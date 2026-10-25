#!/usr/bin/env python3
"""Generate owned SDF assets; never change the upstream PX4 checkout."""
from pathlib import Path
import math
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PX4 = ROOT / 'external/PX4-Autopilot/Tools/simulation/gz'

def material(color):
    return f'<material><ambient>{color}</ambient><diffuse>{color}</diffuse></material>'

def box(name, x, y, z, sx, sy, sz, color):
    return (f'<visual name="{name}"><pose>{x} {y} {z} 0 0 0</pose>'
            f'<geometry><box><size>{sx} {sy} {sz}</size></box></geometry>'
            f'{material(color)}</visual>')

def generate():
    # Preserve all upstream motors / joints, adding two light camera links.
    tree = ET.parse(PX4 / 'models/x500/model.sdf')
    model = tree.getroot().find('model')
    model.set('name', 'x500_pd')
    for name, pose in [('front', '.22 0 .02 0 0 0'),
                       ('down', '.35 0 -.12 0 1.57079632679 0')]:
        model.append(ET.fromstring(f'''<link name="{name}_camera">
          <pose relative_to="base_link">{pose}</pose>
          <inertial><mass>0.01</mass><inertia><ixx>0.00001</ixx><iyy>0.00001</iyy><izz>0.00001</izz></inertia></inertial>
          <visual name="housing"><geometry><box><size>.025 .035 .025</size></box></geometry>{material('.08 .08 .08 1')}</visual>
          <sensor name="{name}" type="camera"><topic>/pd/{name}/image</topic>
            <always_on>true</always_on><update_rate>10</update_rate>
            <camera><horizontal_fov>1.2</horizontal_fov>
              <image><width>640</width><height>480</height><format>R8G8B8</format></image>
              <clip><near>.03</near><far>150</far></clip></camera>
          </sensor></link>'''))
        model.append(ET.fromstring(f'<joint name="{name}_mount" type="fixed"><parent>base_link</parent><child>{name}_camera</child></joint>'))
    tree.write(ROOT / 'src/simulation/models/x500_pd/model.sdf', encoding='unicode')
    (ROOT / 'src/simulation/models/x500_pd/model.config').write_text(
        '<model><name>x500_pd</name><version>1</version><sdf version="1.9">model.sdf</sdf></model>')

    tree = ET.parse(PX4 / 'worlds/default.sdf')
    world = tree.getroot().find('world')
    world.set('name', 'soccer')
    world.find('scene/shadows').text = 'false'
    ground = world.find("model[@name='ground_plane']/link/visual/material")
    for tag in ['ambient', 'diffuse']:
        ground.find(tag).text = '.08 .3 .10 1'
    for system in ['Physics', 'UserCommands', 'SceneBroadcaster', 'Imu',
                   'AirPressure', 'NavSat', 'Magnetometer']:
        filename = {'UserCommands':'user-commands', 'SceneBroadcaster':'scene-broadcaster',
                    'AirPressure':'air-pressure'}.get(system, system.lower())
        world.append(ET.fromstring(f'<plugin filename="gz-sim-{filename}-system" name="gz::sim::systems::{system}"/>'))
    world.append(ET.fromstring('<plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors"><render_engine>ogre</render_engine></plugin>'))
    # Fixed 30 x 20 m amateur practice field, visual markings above the ground.
    visuals = []
    for i in range(10):
        visuals.append(box(f'grass{i}', -13.5+3*i, 0, .006, 3, 20, .01,
                            '.12 .42 .14 1' if i % 2 else '.1 .35 .11 1'))
    for name, x,y,sx,sy in [('left',-15,0,.08,20), ('right',15,0,.08,20),
                            ('top',0,10,30,.08), ('bottom',0,-10,30,.08),
                            ('half',0,0,.08,20)]:
        visuals.append(box(name,x,y,.02,sx,sy,.015,'1 1 1 1'))
    for i in range(80):
        a=2*math.pi*i/80
        visuals.append(box(f'circle{i}',3*math.cos(a),3*math.sin(a),.025,.13,.13,.015,'1 1 1 1'))
    for side in [-1,1]:
        for y in [-2,2]:
            visuals.append(box(f'post{side}_{y}',side*15,y,1,.1,.1,2,'1 1 1 1'))
        visuals.append(box(f'bar{side}',side*15,0,2,.1,4,.1,'1 1 1 1'))
    world.append(ET.fromstring('<model name="pitch"><static>true</static><link name="markings">'+''.join(visuals)+'</link></model>'))
    # White sphere with small black surface panels; visible to the RGB detector.
    ball = '<visual name="white"><geometry><sphere><radius>.11</radius></sphere></geometry>'+material('.95 .95 .95 1')+'</visual>'
    phi=(1+math.sqrt(5))/2
    vertices=[(0,a,b*phi) for a in [-1,1] for b in [-1,1]] + [(a,b*phi,0) for a in [-1,1] for b in [-1,1]] + [(b*phi,0,a) for a in [-1,1] for b in [-1,1]]
    for i, v in enumerate(vertices):
        n=math.sqrt(sum(x*x for x in v)); x,y,z=[.093*x/n for x in v]
        ball += f'<visual name="panel{i}"><pose>{x} {y} {z} 0 0 0</pose><geometry><sphere><radius>.035</radius></sphere></geometry>{material(".015 .015 .015 1")}</visual>'
    world.append(ET.fromstring('<model name="soccer_ball"><pose>0 0 .115 0 0 0</pose><link name="ball"><gravity>false</gravity><inertial><mass>.43</mass><inertia><ixx>.002</ixx><iyy>.002</iyy><izz>.002</izz></inertia></inertial>'+ball+'</link><plugin filename="libpd_ball.so" name="BallMotion"/></model>'))
    world.append(ET.fromstring('<include><uri>model://x500_pd</uri><name>pd_drone</name><pose>0 0 .25 0 0 0</pose></include>'))
    tree.write(ROOT / 'src/simulation/worlds/soccer.sdf', encoding='unicode')

if __name__ == '__main__':
    generate()
