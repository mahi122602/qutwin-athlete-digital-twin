import * as THREE from 'three';
const mix=(a,b,t)=>a+(b-a)*t;
const signInTheta=2.85,signUpTheta=signInTheta-Math.PI;
export function trackPoint(theta,offset=0){return new THREE.Vector3((44+offset)*Math.cos(theta),.65+4.5*Math.pow(Math.max(0,-Math.sin(theta)),3),(31+offset)*Math.sin(theta))}
export function createCameraRig(camera){
function closePose(theta,step=0){
 const a=trackPoint(theta),r=new THREE.Vector3(Math.cos(theta),0,Math.sin(theta)),right=new THREE.Vector3(r.z,0,-r.x);
 const p=a.clone().addScaledVector(r,5.8+step*.12).addScaledVector(right,-.3+step*.1);p.y+=2.25;
 const look=a.clone().addScaledVector(right,theta===signInTheta?1.65:2.2);look.y+=1.42;
 return {pos:p,look,fov:46};
}
const poses={
 wide:{pos:new THREE.Vector3(5,38,91),look:new THREE.Vector3(0,9,-10),fov:46},
 signin:closePose(signInTheta),account:closePose(signUpTheta),body:closePose(signUpTheta,.6),health:closePose(signUpTheta,1.1),review:closePose(signUpTheta,1.5),success:closePose(signUpTheta,1.5)
};
function setCamera(pose,time=0,idle=true){
 camera.position.copy(pose.pos);const look=pose.look.clone();
 if(idle){camera.position.x+=Math.sin(time*.18)*.045;camera.position.y+=Math.sin(time*.24)*.035;look.y+=Math.sin(time*.16)*.018}
 camera.fov=pose.fov||46;camera.up.set(0,1,0);camera.lookAt(look);camera.updateProjectionMatrix();
}
function flightPose(from,to,u,kind='zoom'){
 const a=poses[from],b=poses[to];
 if(kind==='route'){
  const begin=from==='success'||from==='account'||from==='review'?signUpTheta:signInTheta;
  const end=to==='signin'?signInTheta:signUpTheta;
  let angle=begin+(end-begin)*u;
  const edge=trackPoint(angle,8+Math.sin(Math.PI*u)*3);
  edge.y+=2.25+Math.sin(Math.PI*u)*11.5;
  const p=edge;
  const nearStart=1-Math.min(1,u/.14),nearEnd=Math.max(0,(u-.86)/.14);
  if(nearStart>0)p.lerp(a.pos,nearStart*nearStart*(3-2*nearStart));
  if(nearEnd>0)p.lerp(b.pos,nearEnd*nearEnd*(3-2*nearEnd));
  const ahead=trackPoint(angle+(end-begin)*.07);
  ahead.y+=1.7;
  const look=a.look.clone().lerp(ahead,Math.min(1,u/.22));
  look.lerp(b.look,Math.max(0,(u-.72)/.28));
  return {pos:p,look,fov:mix(a.fov,b.fov,u)+Math.sin(Math.PI*u)*4};
 }
 const pos=a.pos.clone().lerp(b.pos,u);pos.y+=Math.sin(Math.PI*u)*7;
 const look=a.look.clone().lerp(b.look,u);
 return {pos,look,fov:mix(a.fov,b.fov,u)+Math.sin(Math.PI*u)*3};
}

return {poses,setCamera,flightPose};
}
