"""Persist sender milestones independently from transport and receiver acceptance."""
import os
from pathlib import Path
from .common import atomic,load,lock,now
STAGES=['DRAFT','SNAPSHOTTED','VERIFIED_FOR_TRANSFER','EXPORTED','RECEIVED','INTEGRITY_VERIFIED','RESTORATION_PLANNED','RESTORED','ACCEPTANCE_PASSED','READY_TO_CONTINUE']
def state_dir(value=None):return Path(value or os.environ.get('GENESIS_RELAY_HOME') or (Path.home()/'.local/state/genesis-relay')).expanduser().absolute()
def record(root,capsule_id,stage=None,**facts):
 root=state_dir(root)
 with lock(root/'registry.lock'):
  data=load(root/'registry.json',{'capsules':{},'history':[]});item=data['capsules'].setdefault(capsule_id,{'capsule_id':capsule_id,'state':'DRAFT','failures':[]})
  if stage:
   if stage not in STAGES:raise ValueError('Unknown Relay state')
   if STAGES.index(stage)<STAGES.index(item['state']):raise ValueError('Milestone regression requires a new capsule')
   if stage=='EXPORTED' and not facts.get('destination_receipt'):raise ValueError('EXPORTED requires an actual destination receipt')
   item['state']=stage
  if facts.get('failure'):item['failures'].append({'at':now(),'message':facts.pop('failure')})
  item.update(facts,updated_at=now());data['history'].append({'capsule_id':capsule_id,'state':item['state'],'at':now(),'facts':facts});atomic(root/'registry.json',data);return item

def status(root=None):return load(state_dir(root)/'registry.json',{'capsules':{},'history':[]})
