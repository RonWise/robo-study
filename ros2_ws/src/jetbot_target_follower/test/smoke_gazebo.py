import json
import subprocess
import time
from pathlib import Path
import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, Float64

rclpy.init()
node=rclpy.create_node('hw1_smoke_check')
state={'visible': None, 'range': None, 'range_at': 0., 'count':0, 'image':None}
def on_range(msg):
 state.update(range=msg.data,range_at=time.monotonic(),count=state['count']+1)
node.create_subscription(Float64,'/target/distance',on_range,10)
node.create_subscription(Bool,'/target/visible',lambda m: state.update(visible=m.data),10)
node.create_subscription(Image,'/target/debug_image',lambda m: state.update(image=m),qos_profile_sensor_data)
def wait_for(predicate,seconds=15):
 until=time.monotonic()+seconds
 while time.monotonic()<until:
  rclpy.spin_once(node,timeout_sec=.1)
  if predicate(): return
 raise AssertionError(str(state))
def move(y):
 result=subprocess.run(['ign','service','-s','/world/hw1_aruco/set_pose',
 '--reqtype','ignition.msgs.Pose','--reptype','ignition.msgs.Boolean','--timeout','3000',
 '--req',f'name: "aruco_target", position: {{x: 0.07982624, y: {y}, z: 0.134705}}'],
 capture_output=True,text=True,check=True)
 assert 'true' in result.stdout,result.stdout+result.stderr
 return time.monotonic()
report={}
try:
 wait_for(lambda: state['visible'] is True and state['range'] is not None and state['image'] is not None)
 assert abs(state['range']-1.5)<.04,state['range']
 report['initial_range_m']=state['range']
 image=CvBridge().imgmsg_to_cv2(state['image'],'bgr8')
 cv2.imwrite('/work/.runtime/hw1-preview.png',image)
 changed=move(2.006)
 wait_for(lambda: state['range_at']>changed+1 and abs(state['range']-2.)<.05)
 report['far_range_m']=state['range']
 changed=move(-1.5)
 wait_for(lambda: state['visible'] is False)
 # Ensure no stale distance updates continue with target behind the camera.
 until=time.monotonic()+1
 while time.monotonic()<until: rclpy.spin_once(node,timeout_sec=.1)
 assert state['visible'] is False and time.monotonic()-state['range_at']>.5
 report['loss_detected']=True
 changed=move(1.5059999)
 wait_for(lambda: state['visible'] is True and state['range_at']>changed+1 and abs(state['range']-1.5)<.04)
 report['reacquired_range_m']=state['range']
 report['motion_publishers']=[name for name,types in node.get_topic_names_and_types() if 'geometry_msgs/msg/Twist' in types]
 assert not report['motion_publishers'],report
 Path('/work/.runtime/hw1-smoke-result.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
finally:
 move(1.5059999)
 node.destroy_node()
 rclpy.shutdown()
