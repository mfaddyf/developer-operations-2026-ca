# OG CODE PUT INTO random_code_4_ca.py, THIS VERSION IS USING FUCTIONS (makes more sense in my mind esp coding with python?)
    # !!! check above in class to make sure this is okay !!!

import sys
import uuid # imported for usage in bucket naming
import boto3
from botocore.exceptions import ClientError, WaiterError

# SETTINGS / VARIABLES --------------
ami_id = 'ami-0fef201115eefe936'
instance_type = 't2.nano'
availability_zone = 'us-east-1b'
key_name = 'awskey'
    # preestablished security group with http + ssh allowed , refactor to create new security group & check if there's one existing already
security_group = 'sg-0fc7eca295775e4d3'
instance_name = f'mroche-inst-{uuid.uuid4().hex[:3]}'

    # startup script - patches os, installs & starts apache, builds index page with instance metadata
    # includes small css styling for the table just to add a personal touch to it 
user_data = """#!/bin/bash
            yum update -y
            yum install httpd -y
            systemctl enable httpd
            systemctl start httpd
            
            TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
            META="http://169.254.169.254/latest/meta-data"
            INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" $META/instance-id)
            PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" $META/public-ipv4)
            AMI_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" $META/ami-id)
            AZ=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" $META/placement/availability-zone)

            cat <<EOF > /var/www/html/index.html
            <html>
            <head>
            <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            table { border-collapse: collapse; }
            th, td { border: 1px solid #999; padding: 8px 16px; text-align: left; }
            th { background-color: #eee; }
            </style>
            </head>
            <body>
            <h1>Madison's DevOps Web Server</h1>
            <h3><i>Built automatically with Python and Boto3 for DevOps Assignment 1!</i></h3>
            <table>
            <tr><th>Instance ID</th><td>$INSTANCE_ID</td></tr>
            <tr><th>Public IP</th><td>$PUBLIC_IP</td></tr>
            <tr><th>AMI ID</th><td>$AMI_ID</td></tr>
            <tr><th>Availability Zone</th><td>$AZ</td></tr>
            </table>
            </body></html>
            EOF
            """

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
            Placement = {'AvailabilityZone': availability_zone},
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
                        }
                    ]
                }
            ])
    except ClientError as error:
        print('Could Not Launch Instance: ', error)
        return None

    instance = new_instances[0]
    print('Instance Launched: ', instance.id)
    print('Instance Name: ', instance_name)
    return instance

def wait_for_instance(instance):
    print('Waiting for instance to start running..!')
    try:
        instance.wait_until_running()
    except WaiterError as error:
        print('Instance Did Not Reach Running State: ', error)
        return False

    instance.reload()
    print('Instance Running! Public IP: ', instance.public_ip_address)
    return True


# BUCKETS ---------------------------
def setup_bucket():
    bucket_name = f'{uuid.uuid4().hex[:6]}-mroche'
    try:
        s3.create_bucket(Bucket=bucket_name)
        print('Bucket Created: ', bucket_name)
    except ClsientError as error:
        print('Could Not Create Bucket: ', error)
        return None

    website_configuration = {
        'ErrorDocument': {'Key': 'error.html'},
        'IndexDocument': {'Suffix': 'index.html'},
    }

    try:
        bucket_website = s3.BucketWebsite(bucket_name)
        bucket_website.put(WebsiteConfiguration=website_configuration)
        print('Status Website Hosting Enabled!')
    except ClientError as error:
        print('Could Not Set Up Website Hosting: ', error)
        return None
        
    return bucket_name


def main():
    instance = launch_instance()
    if instance is None:
        sys.exit(1) # nothing can work without the instance , quit if no instance

    bucket_name = setup_bucket()
    if bucket_name is None:
        print('S3 Setup Failed - Continuing With EC2 Setup')

    if not wait_for_instance(instance):
        print('Remember to Terminate Instance: ', instance.id, 'In The Console!')
        sys.exit(1)

    # more steps cont. here in further steps

if __name__ == '__main__':
    main()
