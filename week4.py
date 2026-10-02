import boto3

user_data = """#!/bin/bash
            yum install httpd -y
            systemctl enable httpd
            systemctl start httpd"""

ec2 = boto3.resource('ec2')
new_instances = ec2.create_instances(
            ImageId='ami-0fef201115eefe936',
            MinCount=1,
            MaxCount=1,
            InstanceType='t2.nano',
            KeyName='awskey',
            # takes the user data from above
            UserData=user_data,
            # security group id inputted for existing secutiry group, maybe change to making a security group & checking if one already exists
            SecurityGroupIds=['sg-0fc7eca295775e4d3'],
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': 'Web Server CI'
                        }]
                }
            ])

# set the new instance under 'instance' , prints the id , waits until its running & reload , prints that it's running
instance = new_instances[0]
print(instance.id)
instance.wait_until_running()
instance.reload()
print('Instance Running...')

# --- buckets below
s3 = boto3.resource('s3')

