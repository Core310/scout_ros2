import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.launch_description_sources import PythonLaunchDescriptionSource

from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

from launch.substitutions import Command, FindExecutable
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessExit


def generate_launch_description():
    # ------------------------------------------------------------------------
    # Declare the use_sim_time argument (for both ROS nodes and rst bridges)
    # ------------------------------------------------------------------------
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation (Gazebo) clock if true'
    )

    # ------------------------------------------------------------------------
    # Paths to your robot description and RViz config
    # ------------------------------------------------------------------------
    pkg_desc = FindPackageShare('scout_description')

    model_name = 'scout2.urdf.xacro'
    model_path = PathJoinSubstitution([pkg_desc, 'urdf', model_name])

    rviz_config = PathJoinSubstitution([pkg_desc, 'rviz', 'model_display.rviz'])

    # ------------------------------------------------------------------------
    # Robot State Publisher (publishes /robot_description via xacro + RSP)
    # ------------------------------------------------------------------------
    robot_description_content = Command([
        PathJoinSubstitution([FindExecutable(name='xacro')]), ' ',
        model_path
    ])
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {'robot_description': robot_description_content}
        ]
    )

    # ------------------------------------------------------------------------
    # Joint State Publisher (for any non-simulated joints)
    # ------------------------------------------------------------------------
    joint_state_publisher = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
    )

    # ------------------------------------------------------------------------
    # RViz2
    # ------------------------------------------------------------------------
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': use_sim_time}],
    )

    # ------------------------------------------------------------------------
    # PointCloudToLaserScan node
    # ------------------------------------------------------------------------
    pcl_to_laserscan = Node(
        package='pointcloud_to_laserscan',
        executable='pointcloud_to_laserscan_node',
        name='pointcloud_to_laserscan',
        output='screen',
        remappings=[
            ('cloud_in', '/ray/pointcloud2'),
            ('scan', '/scan')
        ],
        parameters=[{
            'use_sim_time': use_sim_time,
            'transform_tolerance': 0.05,
            'min_height': 0.0,
            'max_height': 1.0,
            'angle_min': -3.14159,
            'angle_max':  3.14159,
            'angle_increment': 3.14159 / 180.0 / 2.0,
            'scan_time': 1.0/10.0,
            'range_min': 0.1,
            'range_max': 100.0,
            'use_inf': True,
        }],
    )

    # ------------------------------------------------------------------------
    # Launch Ignition/Garden simulator
    # ------------------------------------------------------------------------
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            FindPackageShare('ros_gz_sim'), 'launch', 'gz_sim.launch.py'
        ]),
        launch_arguments={
            # run paused (-r) until spawn, set verbosity to 4, load empty world
            'gz_args': ['-r', '-v', '4', 'empty.sdf']
        }.items()
    )

    # ------------------------------------------------------------------------
    # Start the ROS ↔ Ignition bridge
    # ------------------------------------------------------------------------
    gz_bridge = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            FindPackageShare('ros_gz_bridge'), 'launch', 'parameter_bridge.launch.py'
        ]),
        launch_arguments={
            # this default bridge file will already include /clock, /tf,
            # and common geometry msgs; see config/parameter_bridge.sdf
        }.items()
    )

    # ------------------------------------------------------------------------
    # Spawn the URDF robot into Ignition via the bridge
    # ------------------------------------------------------------------------
    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        name='spawn_scout2',
        output='screen',
        arguments=[
            '-name', 'scout2',
            '-topic', 'robot_description',
            '-allow_renaming', 'true'
        ],
    )

    # ------------------------------------------------------------------------
    # Assemble the full launch description
    # ------------------------------------------------------------------------
    return LaunchDescription([
        declare_use_sim_time,
        LogInfo(msg=['use_sim_time = ', use_sim_time]),

        # core robot description nodes
        robot_state_publisher,
        joint_state_publisher,
        pcl_to_laserscan,

        # simulator, bridge, spawn
        gz_sim,
        gz_bridge,
        spawn_robot,

        # visualization
        rviz_node,
    ])
