from pathlib import Path
import math
import xml.etree.ElementTree as E
import cv2
import numpy as np

root = Path(__file__).resolve().parents[1]
model = root/'models/aruco_target'
dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
marker = cv2.aruco.drawMarker(dictionary, 0, 600)
board = cv2.copyMakeBorder(marker, 100, 100, 100, 100, cv2.BORDER_CONSTANT, value=255)
cv2.imwrite(str(model/'marker_0.png'), board)
# Geometry tiles avoid rendering-engine-dependent UVs and filtering.
sdf = E.Element('sdf', version='1.7')
m = E.SubElement(sdf, 'model', name='aruco_target')
E.SubElement(m, 'static').text='true'
link = E.SubElement(m, 'link', name='board')
def box(name, pos, size, color):
 v=E.SubElement(link,'visual',name=name)
 E.SubElement(v,'pose').text=' '.join(map(str,pos))+' 0 0 0'
 g=E.SubElement(v,'geometry'); b=E.SubElement(g,'box'); E.SubElement(b,'size').text=' '.join(map(str,size))
 mat=E.SubElement(v,'material')
 for tag in ['ambient','diffuse','emissive']: E.SubElement(mat,tag).text=color
 E.SubElement(mat,'specular').text='0 0 0 1'
box('white_margin',(0,0,0),(.32,.01,.32),'1 1 1 1')
for row in range(6):
 for col in range(6):
  if marker[row*100+50,col*100+50] == 0:
   box(f'cell_{row}_{col}', ((col-2.5)*.04,-.0055,(2.5-row)*.04),(.04,.001,.04),'0 0 0 1')
E.indent(sdf)
E.ElementTree(sdf).write(model/'model.sdf',encoding='unicode',xml_declaration=True)
for folder,name in [('aruco_target','aruco_target'),('jetbot_hw1','jetbot_hw1')]:
 (root/'models'/folder/'model.config').write_text(f'<model><name>{name}</name><version>1.0</version><sdf version="1.7">model.sdf</sdf></model>\n')
# Fixed robot pose; derive target placement using the actual source camera extrinsics.
def rot(r,p,y):
 cx,sx=math.cos(r),math.sin(r);cy,sy=math.cos(p),math.sin(p);cz,sz=math.cos(y),math.sin(y)
 return np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]])@np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]])@np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]])
rb=rot(-math.pi/2,0,0)
rc=rot(1.9199,-1.5708,3.1416)
cp=np.array([0,0,.1])+rb@(np.array([.053557,-.057568,0])+rc@np.array([0,.0325,.0125]))
target=cp+(rb@rc)[:,0]*1.5
# Front face is 5 mm in front of board origin: put black tiles at the target distance.
target[1]+=.006
world=f'''<?xml version="1.0"?>
<sdf version="1.7">
  <world name="hw1_aruco">
    <physics name="physics" type="ignored"><max_step_size>0.001</max_step_size><real_time_factor>1</real_time_factor></physics>
    <plugin filename="ignition-gazebo-physics-system" name="ignition::gazebo::systems::Physics"/>
    <plugin filename="ignition-gazebo-user-commands-system" name="ignition::gazebo::systems::UserCommands"/>
    <plugin filename="ignition-gazebo-scene-broadcaster-system" name="ignition::gazebo::systems::SceneBroadcaster"/>
    <plugin filename="ignition-gazebo-sensors-system" name="ignition::gazebo::systems::Sensors"><render_engine>ogre2</render_engine></plugin>
    <scene><ambient>1 1 1 1</ambient><background>0.65 0.7 0.75 1</background><shadows>false</shadows></scene>
    <light name="sun" type="directional"><pose>0 0 5 0 0 0</pose><diffuse>1 1 1 1</diffuse><direction>0 0 -1</direction></light>
    <model name="ground"><static>true</static><link name="link">
      <collision name="collision"><geometry><plane><normal>0 0 1</normal><size>10 10</size></plane></geometry></collision>
      <visual name="visual"><geometry><plane><normal>0 0 1</normal><size>10 10</size></plane></geometry><material><ambient>0.65 0.65 0.65 1</ambient><diffuse>0.65 0.65 0.65 1</diffuse></material></visual>
    </link></model>
    <!-- Stationary perception fixture; motion is a later exercise. -->
    <include><uri>model://jetbot_hw1</uri><name>jetbot</name><static>true</static><pose>0 0 0.1 -1.5707963267948966 0 0</pose></include>
    <!-- 24 cm black square with a 4 cm white margin, about 1.5 m from camera. -->
    <include><uri>model://aruco_target</uri><name>aruco_target</name><pose>{target[0]:.9f} {target[1]:.9f} {target[2]:.9f} 0 0 0</pose></include>
  </world>
</sdf>
'''
(root/'worlds/hw1_aruco.sdf').write_text(world)
print('Camera position:',cp,'Target:',target)
