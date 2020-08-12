import boto3
import botocore
import click

session = boto3.Session(profile_name='shotty')
ec2 = session.resource('ec2')

def filter_instances(project, instance_id):
    instances = []
    if project:
        filters = [{'Name':'tag:Project', 'Values':[project]}]
        instances = ec2.instances.filter(Filters=filters)
    elif instance_id:
        instances = ec2.instances.filter(InstanceIds=[instance_id])
    else:
        instances = ec2.instances.all()
    return instances

def has_pending_snapshot(volume):
    snapshots = list(volume.snapshots.all())
    return snapshots and snapshots[0].state == 'pending'

@click.group()
@click.option('--profile', default=None,
    help="Specify AWSCLI profile to use")
def cli(profile):
    """Shooty manages snapshots"""
    if profile:
        print("The profile {0} was given".format(profile))
        session = boto3.Session(profile_name=profile)
        ec2 = session.resource('ec2')

@cli.group('snapshots')
def snapshots():
    """Commands for volumes"""

@cli.group('volumes')
def volumes():
    """Commands for volumes"""

@cli.group('instances')
def instances():
    """Commands for instances"""

@snapshots.command('list')
@click.option('--project', default=None,
    help="Only snapshots for project (tag Project:<name>)")
@click.option('--all', 'list_all', default=False, is_flag=True,
    help="List all snapshots for each volume, not just the most recent")
@click.option('--instance_id', default=None,
    help="Only instance provided (tag Insantce_ID:<name>)")
def list_snapshots(project, list_all, instance_id):
    "List EC2 volume snapshots"
    instances = filter_instances(project, instance_id)
    for i in instances:
        for v in i.volumes.all():
            for s in v.snapshots.all():
                print(", ".join((
                    s.id,
                    v.id,
                    i.id,
                    s.state,
                    s.progress,
                    s.start_time.strftime("%c")
                )))
                if s.state == 'completed' and not list_all: break
    return

@volumes.command('list')
@click.option('--project', default=None,
    help="Only volumes for project (tag Project:<name>)")
@click.option('--instance_id', default=None,
    help="Only instance provided (tag Insantce_ID:<name>)")
def list_volumes(project, instance_id):
    "List EC2 volumes"
    instances = filter_instances(project, instance_id)
    for i in instances:
        for v in i.volumes.all():
            print(", ".join((
                v.id,
                i.id,
                v.state,
                str(v.size) + "GiB",
                v.encrypted and "Encrypted" or "Not Encrypted"
            )))
    return

@instances.command('snapshot',
    help='Create snapshots for all volumes')
@click.option('--project', default=None,
    help="Only instances for project (tag Project:<name>)")
@click.option('--force', 'force_action', default=False, is_flag=True,
    help="Force action when no project is specified (ALL INSTANCES)")
@click.option('--instance_id', default=None,
    help="Only instance provided (tag Insantce_ID:<name>)")
def create_snapshots(project, force_action, instance_id):
    "Create snapshots for EC2 instances"
    if not (project or force_action or instance_id):
        print("Action requires --force option")
        return
    instances = filter_instances(project, instance_id)
    was_running = False
    for i in instances:
        if i.state['Name'] == 'running':
            was_running = True
            print("Stopping {0}...".format(i.id))
        i.stop()
        i.wait_until_stopped()
        for v in i.volumes.all():
            if has_pending_snapshot(v):
                print("  Skipping {0}, snapshot already in progress".format(v.id))
                continue
            print("Creating snapshot of {0}".format(v.id))
            v.create_snapshot(Description="Created by SnapshotAutomatic 200")
        if was_running:
            print("Starting {0}...".format(i.id))
            i.start()
            i.wait_until_running()
    print("Job's done!")
    return

@instances.command('list')
@click.option('--project', default=None,
    help="Only instances for project (tag Project:<name>)")
@click.option('--instance_id', default=None,
    help="Only instance provided (tag Insantce_ID:<name>)")
def list_instances(project, instance_id):
    "List EC2 Instances"
    instances = filter_instances(project, instance_id)
    for i in instances:
        tags = { t['Key']: t['Value'] for t in i.tags or []}
        print(', '.join((
            i.id,
            i.instance_type,
            i.placement['AvailabilityZone'],
            i.state['Name'],
            i.public_dns_name,
            tags.get('Project', '<no project>')
            )))
    return

@instances.command('stop')
@click.option('--project', default=None,
    help = 'Only instances for project (tag Project:<name>)')
@click.option('--force', 'force_action', default=False, is_flag=True,
    help="Force action when no project is specified (ALL INSTANCES)")
@click.option('--instance_id', default=None,
    help="Only instance provided (tag Insantce_ID:<name>)")
def stop_instances(project, force_action, instance_id):
    "Stop EC2 instances"
    if not (project or force_action or instance_id):
        print("Action requires --force option")
        return
    instances = filter_instances(project, instance_id)
    for i in instances:
        print("Stopping {0}...".format(i.id))
        try:
            i.stop()
        except botocore.exceptions.ClientError as e:
            print(" Couln not stop {0}. ".format(i.id) + str(e))
            continue
    return

@instances.command('start')
@click.option('--project', default=None,
    help = 'Only instances for project (tag Project:<name>)')
@click.option('--force', 'force_action', default=False, is_flag=True,
    help="Force action when no project is specified (ALL INSTANCES)")
@click.option('--instance_id', default=None,
    help="Only instance provided (tag Insantce_ID:<name>)")
def start_instances(project, force_action, instance_id):
    "Start EC2 instances"
    if not (project or force_action or instance_id):
        print("Action requires --force option")
        return
    instances = filter_instances(project, instance_id)
    for i in instances:
        print("Starting {0}...".format(i.id))
        try:
            i.start()
        except botocore.exceptions.ClientError as e:
            print(" Couln not start {0}. ".format(i.id) + str(e))
            continue
    return

@instances.command('reboot')
@click.option('--project', default=None,
    help = 'Only instances for project (tag Project:<name>)')
@click.option('--force', 'force_action', default=False, is_flag=True,
    help="Force action when no project is specified (ALL INSTANCES)")
@click.option('--instance_id', default=None,
    help="Only instance provided (tag Insantce_ID:<name>)")
def reboot_instances(project, force_action, instance_id):
    "Reboot EC2 instances"
    if not (project or force_action or instance_id):
        print("Action requires --force option")
        return
    instances = filter_instances(project, instance_id)
    for i in instances:
        print("Rebooting {0}...".format(i.id))
        try:
            i.reboot()
        except botocore.exceptions.ClientError as e:
            print(" Couln not reboot {0}. ".format(i.id) + str(e))
            continue
    return

if __name__ == '__main__':
    cli()
