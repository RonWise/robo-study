from pathlib import Path
from setuptools import find_packages, setup

package_name = 'jetbot_target_follower'
data_files = [
    ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
    ('share/' + package_name, ['package.xml']),
]
for folder in ('launch', 'config', 'worlds', 'models'):
    for directory in sorted(p for p in Path(folder).rglob('*') if p.is_dir()):
        files = sorted(str(p) for p in directory.iterdir() if p.is_file())
        if files:
            data_files.append(('share/' + package_name + '/' + str(directory), files))
    files = sorted(str(p) for p in Path(folder).iterdir() if p.is_file())
    if files:
        data_files.append(('share/' + package_name + '/' + folder, files))
setup(
    name=package_name, version='0.1.0', packages=find_packages(exclude=['test']),
    data_files=data_files, install_requires=['setuptools'], zip_safe=True,
    maintainer='Roman N.', maintainer_email='7211393+RonWise@users.noreply.github.com',
    description='HW1 ArUco perception and target following in Gazebo Fortress.',
    license='Apache-2.0',
    entry_points={'console_scripts': ['target_detector = jetbot_target_follower.detector:main', 'target_follower = jetbot_target_follower.follower:main', 'command_router = jetbot_target_follower.router:main']},
)
