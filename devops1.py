#!/usr/bin/env python3
import boto3

ec2 = boto3.resource('ec2')
for inst in ec2.instances.all():
    print(inst.id, inst.public_ip_address)

s3 = boto3.resource('s3')
for bucket in s3.buckets.all():
    print(bucket.name)
