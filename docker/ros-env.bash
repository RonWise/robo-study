# ROS setup scripts are not compatible with nounset; restore it afterwards.
_robo_had_nounset=0
case $- in *u*) _robo_had_nounset=1; set +u ;; esac
source /opt/ros/humble/setup.bash
if [[ -f /work/ros2_ws/install/local_setup.bash ]]; then
    source /work/ros2_ws/install/local_setup.bash
fi
if (( _robo_had_nounset )); then set -u; fi
unset _robo_had_nounset
