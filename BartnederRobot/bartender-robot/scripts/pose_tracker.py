#!/usr/bin/env python
"""
Created on Sat May 30 22:31:22 2020

@author: kartik
"""
from __future__ import print_function
import numpy as np
#import matplotlib.pyplot as plt
#import pyquaternion as pyq
import sys
from cv_bridge import CvBridge,CvBridgeError
import rospy
from sensor_msgs.msg import Image
from arm_tracking_planner_executer import Robot
from environment import Environment
from transforms import Transforms
if  '/opt/ros/kinetic/lib/python2.7/dist-packages' in sys.path : sys.path.remove('/opt/ros/kinetic/lib/python2.7/dist-packages') 
import cv2
from cv2 import aruco
from arm_tracking.msg import TrackedPose
from calibrate_transforms import CalibrateTransforms
import time
import traceback

class PoseTracker():
    def __init__(self, robot,env, image_topic):
        self.robot = robot
        self.env = env
        self.bridge = CvBridge()
        self.image_sub = rospy.Subscriber(image_topic, Image, self.get_image)
        self.image = None
        
        #put camera matrices here
        self.camera_instrinsic = np.array(((617.0026849655,-0.153855356,315.5900337131),#fx, s,cx
                   (0,614.4461785395,243.0005874753), ##0,fy,cy
                   (0,0,1) ))
        self.dist = np.array((0.1611730644,-0.3392379107,0.0010744837,0.000905697)) #k1,k2,p1,p2 ie radial dist and tangential dist
        
#        self.camera_instrinsic = np.load('/home/kartik/catkin_ws/src/kinova-ros/ArmTracking/arm_tracking/scripts/camera_intrinsic_matrix/camera_mtx.npy')
#
#        self.dist = np.load('/home/kartik/catkin_ws/src/kinova-ros/ArmTracking/arm_tracking/scripts/camera_intrinsic_matrix/dist_mtx.npy')
        
        self.marker_side = 0.039
        
        #aruco marker tracks all the markers in the frame and returns poses as list, specify which pose belongs to what 
        self.robot_base_id,self.robot_ef_id, self.workpiece_id = 1,0,2
        self.pub = rospy.Publisher('arm_tracking/tracked_image',Image, queue_size=10)
        self.pose_tracking_pub = rospy.Publisher('arm_tracking/pose_tracking',TrackedPose,queue_size=10)
        self.pose_tracking_sub = rospy.Subscriber('arm_tracking/pose_tracking',TrackedPose,self.get_tracked_pose)
#        self.numpy_sub = rospy.Subscriber('numpy_float',TrackedPose,self.numpy_sub_fun)
#        self.tracked_pose = TrackedPose()
        self.prev_tracked_pose = None        
        
    def get_tracked_pose(self,tracked_pose):
        self.tracked_pose = tracked_pose
            
    def get_image(self,Image):
        try:
            self.image = self.bridge.imgmsg_to_cv2(Image,desired_encoding = 'bgr8')
            self.estimate_pose(self.image,self.marker_side,self.camera_instrinsic,self.dist)
        except CvBridgeError as e:
            print (e)

#    takes cv image and publishes as Image
    def publish_image(self,cvImage):
        try:
            Image = self.bridge.cv2_to_imgmsg(cvImage,encoding = 'bgr8')
            self.pub.publish(Image)
            
        except CvBridgeError as e:
            print (e)  
            
#   given the 3 aruco markers, this gets which marker belongs to which object
#    def assign_markers(self,centers):
#        x_indices = [pt[0] for pt in centers]
#        y_indices = [pt[1] for pt in centers]
#        self.robot_base_id, self.workpiece_id = np.argmax(x_indices),np.argmax(y_indices)
#        self.robot_ef_id = int(3 - self.workpiece_id - self.robot_base_id)        
#     
#    def assign_markers(self,ids):
#        self.robot_base_id = np.where(ids[:,0] == 1)[0][0]
#        self.robot_ef_id = np.where(ids[:,0] == 0)[0][0]
#        self.workpiece_id = np.where(ids[:,0] == 2)[0][0]
        

                        
            
    def estimate_pose(self,frame, marker_side, camera_instrinsic,dist):
        try:
            tracked_pose_msg = TrackedPose()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            aruco_dict = aruco.Dictionary_get(aruco.DICT_4X4_250)
            # detector parameters can be set here (List of detection parameters[3])
            parameters =  aruco.DetectorParameters_create()
            #parameters.adaptiveThreshConstant = 10
            
            corners, ids, rejectedImgPoints = aruco.detectMarkers(gray, aruco_dict, parameters=parameters)
            output = ['']*ids.shape[0]
            for i,id_ in enumerate(ids):
                # estimate pose of each marker and return the values
                # rvet and tvec-different from camera coefficients
                    rvec, tvec, _ = aruco.estimatePoseSingleMarkers(corners[i], marker_side, camera_instrinsic, dist)
                    output[id_[0]] = ([rvec,tvec,corners[i]])
            
            frame_markers = aruco.drawDetectedMarkers(frame.copy(), corners, ids)
            
            tracked_pose_msg.robot_base_rvec = output[self.robot_base_id][0].squeeze()
            tracked_pose_msg.robot_base_tvec = output[self.robot_base_id][1].squeeze()
            tracked_pose_msg.robot_ef_rvec   = output[self.robot_ef_id][0].squeeze()
            tracked_pose_msg.robot_ef_tvec   = output[self.robot_ef_id][1].squeeze()
#            tracked_pose_msg.workpiece_rvec   = output[self.workpiece_id][0].squeeze()
#            tracked_pose_msg.workpiece_tvec   = output[self.workpiece_id][1].squeeze()
#            tracked_pose_msg.workpiece_corners_x = np.sort((output[self.workpiece_id][2].squeeze())[:,0])
#            tracked_pose_msg.workpiece_corners_y = np.sort((output[self.workpiece_id][2].squeeze())[:,1])
            tracked_pose_msg.robot_ef_corners_x = np.sort((output[self.robot_ef_id][2].squeeze())[:,0])
            tracked_pose_msg.robot_ef_corners_y = np.sort((output[self.robot_ef_id][2].squeeze())[:,1])
            
            self.prev_tracked_pose = tracked_pose_msg
            
#            tracked_pose_msg.workpiece_corners_x = tracked_pose_msg.workpiece_corners_x.tolist()
#            tracked_pose_msg.workpiece_corners_y = tracked_pose_msg.workpiece_corners_y.tolist()
            tracked_pose_msg.robot_ef_corners_x = tracked_pose_msg.robot_ef_corners_x.tolist()
            tracked_pose_msg.robot_ef_corners_y = tracked_pose_msg.robot_ef_corners_y.tolist()
            
            self.pose_tracking_pub.publish(tracked_pose_msg)
            self.publish_image(frame_markers)
            text = "Successfully Tracking " + str(len(output))+" markers"
#            rospy.loginfo(tracked_pose_msg.workpiece_corners_x)
#            rospy.loginfo(text)
            return output
        except Exception:
#            pass
#            traceback.print_exc()
            rospy.logerr('Not able to track')
    
    def get_robot_and_workpiece_pose(self):
        poses = self.estimate_pose(self.image,self.marker_side,self.camera_instrinsic,self.dist)
        if len(poses) != 3:
            rospy.logerr('Only '+ str(len(poses))+' markers visible in the image')
        else:
            rospy.loginfo("SUCCEESSSS")
    
    
    def calibrate_transforms(self,load = True):
#        rvec_rb = self.tracked_pose.robot_base_rvec
#        R_c_rb,_ = cv2.Rodrigues(rvec_rb)
        calibratetransform = CalibrateTransforms(self.robot,load)
        R_c_rb = calibratetransform.perform_calibration() #the orientation of the robot frame w.r.t to the camera frame
        self.transform = Transforms(R_c_rb)
        
        rospy.loginfo(self.transform.R_cb)
        return True    
    
    #get robot ef position (x,y,z) in robot frame using camera tracking
    def get_robot_ef_position(self):
#        self.calibrate_transforms()
#        poses = self.estimate_pose(self.image,self.marker_side,self.camera_instrinsic,self.dist)
#        p_cr = poses[self.robot_ef_id][1] #get tvec from aruco marker
        p_cr = self.tracked_pose.robot_ef_tvec
        return self.transform.get_pos_rframe(p_cr)

#        try:
#            print(type(self.image))
#            self.calibrate_transforms()
#            poses = self.estimate_pose(self.image,self.marker_side,self.camera_instrinsic,self.dist)
#            p_cr = poses[self.robot_ef_id][1] #get tvec from aruco marker
#            return self.transform.get_pos_rframe(p_cr[0])
#        except:
#            rospy.logerr('Not able to track')
            
        
    #gets robot ef pose(6D) in robot frame using moveit or robot
    def get_robot_pose(self):
#        robot_pose = self.robot.group.get_current_pose().pose.position
        robot_pose = self.robot.get_end_effector_pose().position
        robot_pose = np.array((robot_pose.x,robot_pose.y,robot_pose.z))
        return robot_pose
        
    def get_workpiece_marker_position(self):
#        poses = self.estimate_pose(self.image,self.marker_side,self.camera_instrinsic,self.dist)
#        p_cr = poses[self.workpiece_id][1] #get tvec from aruco marker
        p_cw = self.tracked_pose.workpiece_tvec
        return self.transform.get_pos_rframe(p_cw)
        
    def get_workpiece_edge(self,num_of_points_traj):
        shape = self.env.workpiece_size
#        target_end_points = np.linspace((-shape[0]/2,shape[1]/2,shape[2]/2,1),(shape[0]/2,shape[1]/2,shape[2]/2,1),10)
        target_end_points = np.linspace((-shape[0]/2,shape[1],shape[2]/2,1),(shape[0]/2,shape[1],shape[2],1),num_of_points_traj)
        transformation_matrix = np.identity(4)
        transformation_matrix [:3,3] = self.env.workpiece_pose[:3] #dx,dy,dz
        
        workpiece_edge_points = (np.dot(transformation_matrix,target_end_points.T)).T[:,:3]
        return workpiece_edge_points
    

if __name__ == '__main__':
    robot = Robot('kinova','real')
    env = Environment(robot)
#    env.add_all_objects()    
    posetracker = PoseTracker(robot,env, image_topic='/camera/color/image_raw')
    time.sleep(2)
##    
    while(1):
        if posetracker.image is not None:
#            posetracker.get_workpiece_marker_position()
            posetracker.calibrate_transforms(load = False)
            break

#    while(1):    
#        error = (posetracker.get_robot_ef_position() - posetracker.get_workpiece_marker_position())
#        print(np.round(posetracker.tracked_pose.robot_ef_tvec,3),np.round(posetracker.tracked_pose.workpiece_tvec,3),np.round(posetracker.tracked_pose.robot_base_tvec,3), 
#        np.round(posetracker.tracked_pose.robot_ef_rvec,3),np.round(posetracker.tracked_pose.workpiece_rvec,3),np.round(posetracker.tracked_pose.robot_base_rvec,3))
##        diff = error - prev_error
##        if np.sum(np.abs(diff))> 0 : 
##            print(diff)
#            
#        prev_error = error
#            
##            posetracker.get_robot_and_workpiece_pose()
##    while(1):
##        if posetracker.image is not None:
###            image = posetracker.image.copy()
##            cv2.namedWindow( "Display window") 
##            cv2.imshow( "Display window", posetracker.image)
##            cv2.waitKey(3)
    rospy.spin()    
#    
#        
#        
