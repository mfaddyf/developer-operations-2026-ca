# OG CODE PUT INTO random_code_4_ca.py, THIS VERSION IS USING FUCTIONS (makes more sense in my mind esp coding with python?)
	# !!! check above in class to make sure this is okay !!!

import sys
import uuid # imported for usage in bucket naming
import boto3

# SETTINGS / VARIABLES --------------
ami_id = 'ami-0fef201115eefe936'
instance_type = 't2.nano'
availability_zone = 'us-east-1b'
key_name = 'awskey'
	# preestablished security group with http + ssh allowed , refactor to create new security group & check if there's one existing already
security_group = 'sg-0fc7eca295775e4d3'
instance_name = 'mroche-web-server'

	# startup script - patches os installs & starts apache
user_data = """#!/bin/bash
            yum update -y
            yum install httpd -y
            systemctl enable httpd
            systemctl start httpd"""
            
ec2 = boto3.resource('ec2')
s3 = boto3.resource('s3')

# EC2 -------------------------------
def launch_instance():
	try:
	new_instances = ec2.create_instances(
            ImageId = ami_id,
            MinCount = 1,
            MaxCount = 1,
            InstanceType = instance_type,
            Placement = {'AvailabilityZone': availabilty_zone},
            KeyName = key_name,
            # takes the user data from above
            UserData = user_data,
            # security group id inputted for existing secutiry group, maybe change to making a security group & checking if one already exists
            SecurityGroupIds = [security_group],
            TagSpecifications = [
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': instance_name
                        }]
                }
            ])
            
def wait_for_instance():

def setup_bucket():

def main():
