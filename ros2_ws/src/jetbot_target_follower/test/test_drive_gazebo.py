"""Integration test for drive_sim.launch.py (domain 45, only virtual entities)."""
import json
import math
from pathlib import Path
import subprocess
import time
import unittest

import rclpy
from geometry_msgs.msg import Twist
from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue
from rcl_interfaces.srv import SetParameters
from std_msgs.msg import String, Float64, Bool
from tf2_msgs.msg import TFMessage


def run_trials():
    rclpy.init()
    n=rclpy.create_node('hw1_drive_acceptance')
    s={'pose':None,'state':None,'range':None,'cmd':None,'visible':False}
    def pose(msg):
        for t in msg.transforms:
            if t.child_frame_id=='jetbot':
                s['pose']=(t.transform.translation.x,t.transform.translation.y,t.transform.translation.z)
    n.create_subscription(TFMessage,'/simulation/poses',pose,10)
    n.create_subscription(String,'/follower/state',lambda m:s.update(state=m.data),10)
    n.create_subscription(Float64,'/target/base_distance',lambda m:s.update(range=m.data),10)
    n.create_subscription(Bool,'/target/visible',lambda m:s.update(visible=m.data),10)
    n.create_subscription(Twist,'/cmd_vel',lambda m:s.update(cmd=(m.linear.x,m.angular.z)),10)
    teleop=n.create_publisher(Twist,'/cmd_vel_teleop',1)
    client=n.create_client(SetParameters,'/target_follower/set_parameters')
    assert client.wait_for_service(timeout_sec=10)
    def spin(seconds,command=None):
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            if command is not None:teleop.publish(command)
            rclpy.spin_once(n,timeout_sec=.025)
            time.sleep(.01)
    def enable(value):
        request=SetParameters.Request(parameters=[Parameter(name='enabled',value=ParameterValue(type=ParameterType.PARAMETER_BOOL,bool_value=value))])
        f=client.call_async(request);rclpy.spin_until_future_complete(n,f,timeout_sec=5)
        assert f.result() is not None and f.result().results[0].successful
    def service(name,kind,request):
        result=subprocess.run(['ign','service','-s','/world/hw1_drive/'+name,'--reqtype',kind,
                               '--reptype','ignition.msgs.Boolean','--timeout','4000','--req',request],
                              text=True,capture_output=True,check=True)
        assert 'true' in result.stdout,result.stdout+result.stderr
    def reset(x=0.,y=0.,yaw=0.):
        enable(False);spin(.6,Twist())
        a=math.sin(yaw/2)/math.sqrt(2);b=math.cos(yaw/2)/math.sqrt(2)
        service('set_pose','ignition.msgs.Pose',f'name:"jetbot",position:{{x:{x},y:{y},z:0.08}},orientation:{{x:{-b},y:{-a},z:{a},w:{b}}}')
        spin(1.5)
        assert s['visible'],s
        enable(True);s['state']=None
    def arrive(timeout=45):
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            rclpy.spin_once(n,timeout_sec=.05)
            if s['state']=='ARRIVED':
                spin(.7)
                d=math.hypot(1.6-s['pose'][0],s['pose'][1])
                assert .375<d<.625,('ground truth',d,s)
                assert abs(s['cmd'][0])+abs(s['cmd'][1])<1e-6,s
                return round(d,4)
        raise AssertionError('Did not arrive: '+str(s))
    report={'attempts':[]}
    try:
        for x,y,yaw in [(0.,0.,0.),(0.,-.25,.15),(0.,.25,-.15),(.25,-.15,0.),(.2,.2,-.25)]:
            reset(x,y,yaw)
            distance=arrive()
            result={'start':[x,y,yaw],'actual_stop_distance_m':distance}
            report['attempts'].append(result)
            print(json.dumps(result),flush=True)
        # A train of zero teleop messages must not indefinitely mask navigation.
        reset()
        spin(1.,Twist())
        assert s['cmd'][0]>.01,s
        report['idle_teleop_does_not_block']=True
        manual=Twist();manual.angular.z=.5
        spin(2.8,manual)
        assert s['state']=='MANUAL' and s['cmd'][1]>.4,s
        assert not s['visible'],s
        spin(.35,Twist())
        assert s['state']!='MANUAL',s
        report['teleop_recovery_stop_m']=arrive(45)
        print('Teleop recovery passed',flush=True)
        # A real occluding box, not a fabricated detector result.
        reset()
        sdf='<sdf version="1.7"><model name="hw1_occluder"><static>true</static><pose>0.8 0 0.5 0 0 0</pose><link name="link"><visual name="visual"><geometry><box><size>0.03 1 1</size></box></geometry><material><ambient>0.3 0.3 0.3 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model></sdf>'
        service('create','ignition.msgs.EntityFactory','sdf: '+json.dumps(sdf))
        spin(2.)
        assert not s['visible'] and s['state'] in ('LOST','SEARCH'),s
        service('remove','ignition.msgs.Entity','name:"hw1_occluder",type:MODEL')
        report['occlusion_recovery_stop_m']=arrive(45)
        print('Occlusion recovery passed',flush=True)
        # Loss of camera frames must stop rather than search blindly.
        reset();spin(1.)
        service('control','ignition.msgs.WorldControl','pause:true')
        try:
            spin(1.3)
            assert s['state']=='NO_IMAGE' and abs(s['cmd'][0])+abs(s['cmd'][1])<1e-6,s
            report['camera_pause_stops_robot']=True
        finally:service('control','ignition.msgs.WorldControl','pause:false')
        report['resume_after_pause_stop_m']=arrive()
        Path('/work/.runtime/hw1-drive-tests.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)
    finally:
        enable(False);spin(.5,Twist())
        n.destroy_node();rclpy.shutdown()


# Deliberately not a unittest case: run explicitly against a running simulated world.
if __name__=='__main__':run_trials()
