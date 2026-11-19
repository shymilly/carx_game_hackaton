"""Place posters on clear wall piers, considering rendered mesh bounds, not just collision."""
from pathlib import Path
from itertools import product
import json,math
import unreal as ue

root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem);actors=ue.get_editor_subsystem(ue.EditorActorSubsystem)
assert levels.load_level('/Game/Locations/L_NeptuneStreet')
placed=actors.get_all_level_actors()
def bounds_box(a):
 p,e=a.get_actor_bounds(False)
 return (p.x-e.x,p.x+e.x,p.y-e.y,p.y+e.y,p.z-e.z,p.z+e.z)
def span(b,v):
 values=[v.x*x+v.y*y for x,y in product(b[:2],b[2:4])]
 return min(values),max(values)
def transformed_bounds(box,tr):
 ps=[ue.MathLibrary.transform_location(tr,ue.Vector(x,y,z)) for x,y,z in product((box.min.x,box.max.x),(box.min.y,box.max.y),(box.min.z,box.max.z))]
 return (min(p.x for p in ps),max(p.x for p in ps),min(p.y for p in ps),max(p.y for p in ps),min(p.z for p in ps),max(p.z for p in ps))

structures=[(a,bounds_box(a)) for a in placed if a.actor_has_tag('ProportionalHouseVolume')]
rendered=[]
for a in placed:
 if a.actor_has_tag('PreservedImageAspect') or a.get_editor_property('hidden') or 'sky' in a.get_actor_label().lower():continue
 aggregate=bounds_box(a)
 # Keep relevant low facade details, excluding sky, horizon and factory.
 if aggregate[5]<40 or aggregate[4]>1000 or abs(a.get_actor_location().x)>11000:continue
 for c in a.get_components_by_class(ue.StaticMeshComponent):
  if not c.static_mesh or not c.get_editor_property('visible'):continue
  box=c.static_mesh.get_bounding_box()
  if isinstance(c,ue.InstancedStaticMeshComponent):
   transforms=(c.get_instance_transform(i,True) for i in range(c.get_instance_count()))
  else:transforms=(c.get_world_transform(),)
  for tr in transforms:
   b=transformed_bounds(box,tr)
   if b[5]>=40 and b[4]<=1000:rendered.append((a.get_name(),b))

records=[]
for a in placed:
 if not a.actor_has_tag('PreservedImageAspect'):continue
 p=a.get_actor_location();n=a.get_actor_right_vector();t=a.get_actor_forward_vector()
 b=bounds_box(a);half_height=(b[5]-b[4])/2;half_width=21.5
 candidates=[]
 for body,box in structures:
  front=span(box,n)[1];lo,hi=span(box,t)
  q=p.x*t.x+p.y*t.y
  if abs(p.x*n.x+p.y*n.y-front-2)<1 and lo<q<hi:candidates.append((body,box,front,lo,hi))
 assert len(candidates)==1,(a.get_actor_label(),len(candidates))
 original=candidates[0]
 def distance(item):
  _,bb=item
  return ((bb[0]+bb[1])/2-p.x)**2+((bb[2]+bb[3])/2-p.y)**2
 # A fully glazed facade uses a neighboring wall instead of hiding the paper behind glass.
 alternatives=[(body,bb,span(bb,n)[1],*span(bb,t)) for body,bb in sorted(structures,key=distance) if body!=original[0]]
 choices=[]
 for body,box,front,lo,hi in [original]+alternatives:
  blocked=[]
  for owner,obstacle in rendered:
   if owner==body.get_name():continue
   near,far=span(obstacle,n)
   if far<front+.5 or near>front+155:continue
   left,right=span(obstacle,t)
   blocked.append((left,right,obstacle[4],obstacle[5]))
  for record in records:
   if record['wall_id']!=body.get_name():continue
   pp=ue.Vector(*record['position'])
   if abs(pp.x*n.x+pp.y*n.y-front-2)>1:continue
   tangent=pp.x*t.x+pp.y*t.y
   blocked.append((tangent-21.5,tangent+21.5,pp.z-record['half_height'],pp.z+record['half_height']))
  old=p.x*t.x+p.y*t.y
  heights=[151.,130.,175.]+list(range(210,int(min(850,box[5]-half_height-35)),20))
  for z in heights:
   for step in range(int((hi-lo-110)/10)+1):
    q=lo+55+step*10
    if any(q+half_width+5>left and q-half_width-5<right and z+half_height+4>bottom and z-half_height-4<top for left,right,bottom,top in blocked):continue
    choices.append((abs(q-old)+abs(z-151)*2,q,z))
  if choices:break
 assert choices,'No clear wall available: '+a.get_actor_label()
 _,q,z=min(choices)
 target=n*(front+2)+t*q;target.z=z
 a.set_actor_location(target,False,True)
 records.append(dict(poster=a.get_actor_label(),wall=body.get_actor_label(),wall_id=body.get_name(),position=[target.x,target.y,target.z],half_height=half_height,rendered_obstacles=len(blocked),clear=True))
assert len(records)==17
assert levels.save_current_level()
(root/'Resources/StreetArtPass/PosterPlacement.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
ue.log('WALL_ADVERT_PLACEMENT_PASSED '+str(len(records)))
