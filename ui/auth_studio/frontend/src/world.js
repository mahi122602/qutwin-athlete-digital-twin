import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';
import { Water } from 'three/addons/objects/Water.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { createCameraRig, trackPoint } from './camera.js';

const TAU = Math.PI * 2;
const asset = path => new URL('../assets/' + path, document.baseURI).href;
// Runtime bundle is at frontend/app.js, so assets are a sibling directory.
const assetURL = path => new URL('assets/' + path, document.baseURI).href;

export async function createWorld(canvas, onProgress = () => {}) {
  const scene = new THREE.Scene();
  const renderer = new THREE.WebGLRenderer({canvas, antialias:true, powerPreference:'high-performance', preserveDrawingBuffer:true});
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = .95;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.shadowMap.autoUpdate = false;
  const camera = new THREE.PerspectiveCamera(46, 16/9, .12, 1400);
  const rig = createCameraRig(camera);
  let seed=736;
  const random=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;};
  const manager = new THREE.LoadingManager();
  manager.onProgress = (url,n,total) => onProgress(n,total);
  const textureLoader = new THREE.TextureLoader(manager);
  const gltfLoader = new GLTFLoader(manager);
  const tex = {};
  const names = ['bronze.png','limestone.png','panorama.png','reference-dawn.png','reference-dusk.png',
    'marble_tiles_Diffuse.jpg','marble_tiles_nor_gl.jpg','marble_tiles_arm.jpg',
    'marble_01_Diffuse.jpg','marble_01_nor_gl.jpg','marble_01_arm.jpg',
    'aerial_grass_rock_Diffuse.jpg','aerial_grass_rock_nor_gl.jpg'];
  const models={};
  const modelNames=['island_tree_01','tree_small_02','shrub_04','rock_09','fern_02','grass_medium_01','pine_sapling_small',
                   'athlete','runner','coach'];
  await Promise.all([
    ...names.map(async name=>{
      const t=await textureLoader.loadAsync(assetURL(name));
      t.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());
      if(!name.includes('nor_gl')&&!name.includes('_arm'))t.colorSpace=THREE.SRGBColorSpace;
      if(!name.includes('reference')&&!name.includes('panorama')){
        t.wrapS=t.wrapT=THREE.RepeatWrapping;
      }
      tex[name]=t;
    }),
    ...modelNames.map(async name=>{
      const model=(await gltfLoader.loadAsync(assetURL('models/'+name+'.glb'))).scene;
      // These source assets contain a display row of variants. Place a single
      // variant per instance, not the source asset's entire display arrangement.
      models[name]=['grass_medium_01','fern_02','pine_sapling_small'].includes(name)?model.children[0]:model;
    }),
    (async()=>{
      const hdr=await new RGBELoader(manager).loadAsync(assetURL('sunrise.hdr'));
      hdr.mapping=THREE.EquirectangularReflectionMapping;
      const pmrem=new THREE.PMREMGenerator(renderer);
      scene.environment=pmrem.fromEquirectangular(hdr).texture;
      hdr.dispose();pmrem.dispose();
    })()
  ]);
  const architecture=[];
  function add(geo,mat,pos=null){
    const m=new THREE.Mesh(geo,mat);if(pos)m.position.copy(pos);
    m.castShadow=m.receiveShadow=true;scene.add(m);architecture.push(m);return m;
  }
  function worldUV(geo,repeat=4){
    const p=geo.attributes.position,n=geo.attributes.normal,uv=geo.attributes.uv;
    for(let i=0;i<p.count;i++){
      if(Math.abs(n.getY(i))>.5)uv.setXY(i,p.getX(i)/repeat,p.getZ(i)/repeat);
      else if(Math.abs(n.getX(i))>.5)uv.setXY(i,p.getZ(i)/repeat,p.getY(i)/repeat);
      else uv.setXY(i,p.getX(i)/repeat,p.getY(i)/repeat);
    }
    return geo;
  }
  const floor=new THREE.MeshPhysicalMaterial({
    map:tex['marble_01_Diffuse.jpg'],normalMap:tex['marble_01_nor_gl.jpg'],
    normalScale:new THREE.Vector2(.12,.12),
    color:0xf7edd9,roughness:.35,metalness:.015,envMapIntensity:.8,clearcoat:.15,clearcoatRoughness:.45
  });
  floor.onBeforeCompile=shader=>{
    shader.vertexShader='varying vec2 vFloorWorld;\n'+shader.vertexShader;
    shader.vertexShader=shader.vertexShader.replace('#include <project_vertex>',
      '#include <project_vertex>\nvFloorWorld=(modelMatrix*vec4(transformed,1.)).xz;');
    shader.fragmentShader='varying vec2 vFloorWorld;\n'+shader.fragmentShader;
    shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>',
      '#include <map_fragment>\nvec2 seam=abs(fract(vFloorWorld/2.)-.5);\nfloat joint=smoothstep(.497,.5,max(seam.x,seam.y));\ndiffuseColor.rgb*=1.-joint*.12;');
  };
  const limestone=new THREE.MeshStandardMaterial({map:tex['marble_01_Diffuse.jpg'],normalMap:tex['marble_01_nor_gl.jpg'],
    roughness:.62,normalScale:new THREE.Vector2(.25,.25),color:0xe9dfca,envMapIntensity:.65});
  const bronze=new THREE.MeshPhysicalMaterial({map:tex['bronze.png'],color:0xb47a4e,
    bumpMap:tex['bronze.png'],bumpScale:.0025,roughness:.29,metalness:.86,envMapIntensity:1.15,clearcoat:.18,clearcoatRoughness:.32});
  const led=new THREE.MeshStandardMaterial({color:0xffe1ac,emissive:0xffbc64,emissiveIntensity:2.8,roughness:.5});
  const dark=new THREE.MeshStandardMaterial({color:0x2a342a,roughness:.8});
  const soil=new THREE.MeshStandardMaterial({map:tex['aerial_grass_rock_Diffuse.jpg'],normalMap:tex['aerial_grass_rock_nor_gl.jpg'],
    roughness:1,normalScale:new THREE.Vector2(.35,.35),color:0x7b8065});
  function box(x,y,z,w,h,d,mat=limestone,bevel=.035){
    const g=worldUV(new RoundedBoxGeometry(w,h,d,2,Math.min(bevel,w/5,h/5,d/5)));
    return add(g,mat,new THREE.Vector3(x,y+h/2,z));
  }
  function flatEllipse(rx,rz,y,mat){
    const g=new THREE.CircleGeometry(1,192),p=g.attributes.position,uv=g.attributes.uv;
    for(let i=0;i<p.count;i++)uv.setXY(i,p.getX(i)*rx/6,p.getY(i)*rz/6);
    const m=add(g,mat,new THREE.Vector3(0,y,0));m.rotation.x=-Math.PI/2;m.scale.set(rx,rz,1);return m;
  }
  function band(rx,rz,width,y,mat){
    const points=[],uv=[],indices=[];
    for(let i=0;i<=240;i++){
      const a=i/240*TAU;
      for(const d of [0,width]){const x=(rx+d)*Math.cos(a),z=(rz+d)*Math.sin(a);points.push(x,y,z);uv.push(x/6,z/6);}
    }
    for(let i=0;i<240;i++){const j=i*2;indices.push(j,j+2,j+1,j+1,j+2,j+3);}
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(points,3));
    g.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));g.setIndex(indices);g.computeVertexNormals();return add(g,mat);
  }
  function tube(points,r,mat=bronze,segments=240){
    return add(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points),segments,r,6,false),mat);
  }
  const terrainHeight=(x,z)=>{
    const r=Math.hypot(x,z);
    const ramp=THREE.MathUtils.smoothstep(r,79,170);
    return ramp*(1.2+.6*Math.sin(x*.037)+.5*Math.sin(z*.043))-.12;
  };
  {
    const g=new THREE.PlaneGeometry(600,600,200,200);g.rotateX(-Math.PI/2);
    const p=g.attributes.position,uv=g.attributes.uv;
    for(let i=0;i<p.count;i++){
      const x=p.getX(i),z=p.getZ(i);p.setY(i,terrainHeight(x,z));uv.setXY(i,x/12,z/12);
    }
    g.computeVertexNormals();add(g,soil);
  }
  // A single geometric loop. No scene plates are exchanged during movement.
  {
    const pos=[],uv=[],indices=[],n=384;
    for(let i=0;i<=n;i++)for(const off of [-3.2,3.2]){
      const p=trackPoint(i/n*TAU,off);pos.push(p.x,p.y,p.z);uv.push(i/n*43,(off+3.2)/6.4);
    }
    for(let i=0;i<n;i++){const j=i*2;indices.push(j,j+2,j+1,j+1,j+2,j+3);}
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));
    g.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));g.setIndex(indices);g.computeVertexNormals();
    bronze.side=THREE.DoubleSide;add(g,bronze);
    for(const off of [-3.2,3.2]){
      const p=[],u=[],ind=[];
      for(let i=0;i<=n;i++){
        const v=trackPoint(i/n*TAU,off);p.push(v.x,.08,v.z,v.x,v.y-.015,v.z);u.push(i/n*43,0,i/n*43,v.y/2);
      }
      for(let i=0;i<n;i++){const j=i*2;ind.push(j,j+1,j+2,j+1,j+3,j+2);}
      const wall=new THREE.BufferGeometry();wall.setAttribute('position',new THREE.Float32BufferAttribute(p,3));
      wall.setAttribute('uv',new THREE.Float32BufferAttribute(u,2));wall.setIndex(ind);wall.computeVertexNormals();add(wall,bronze);
      const line=[];
      for(let i=0;i<=n;i++){const v=trackPoint(i/n*TAU,off*.987);v.y+=.024;line.push(v);}
      tube(line,.024,led,384);
    }
    for(const off of [-1.05,1.05]){
      const line=[];for(let i=0;i<=n;i++){const v=trackPoint(i/n*TAU,off);v.y+=.015;line.push(v);}
      tube(line,.008,new THREE.MeshStandardMaterial({color:0xd5ad74,metalness:.7,roughness:.35}),384);
    }
  }
  flatEllipse(40.3,27.5,.17,floor);
  band(36.2,23.6,2.3,.20,soil);
  band(58,45,7,.16,floor);
  // Reflective water is rendered from this same scene's mirror camera.
  const waterNormal=await textureLoader.loadAsync(assetURL('waternormals.jpg'));
  waterNormal.wrapS=waterNormal.wrapT=THREE.RepeatWrapping;
  const water=new Water(new THREE.CircleGeometry(1,192),{
    textureWidth:512,textureHeight:512,waterNormals:waterNormal,
    sunDirection:new THREE.Vector3(-.72,.45,-.45).normalize(),sunColor:0xffdda0,
    waterColor:0x37594b,distortionScale:.23,fog:true
  });
  water.rotation.x=-Math.PI/2;water.scale.set(58,45,1);water.position.y=.04;
  scene.add(water);
  // A limestone welcome terrace and steps at each end, at the same track coordinates.
  const inTheta=2.85,upTheta=inTheta-Math.PI;
  for(const theta of [inTheta,upTheta]){
    const a=trackPoint(theta),r=new THREE.Vector3(Math.cos(theta),0,Math.sin(theta)),t=new THREE.Vector3(-r.z,0,r.x);
    const group=new THREE.Group();scene.add(group);
    for(let i=0;i<7;i++){
      const p=a.clone().addScaledVector(r,4+i*.68).addScaledVector(t,6.8);
      const m=box(p.x,.08,p.z,1.1,Math.max(.18,a.y-.08-i*.075),11,limestone,.045);m.rotation.y=-theta;
      const l=box(p.x,.08+Math.max(.18,a.y-.08-i*.075)-.03,p.z,.02,.018,10.8,led,.005);l.rotation.y=-theta;
    }
    // Individual inlaid paving and small material joints make the landing read at eye level.
    for(let i=-5;i<=5;i++){
      const p=a.clone().addScaledVector(t,i*.82);
      const b=box(p.x,a.y+.006,p.z,5.8,.026,.79,floor,.008);b.rotation.y=-theta;
    }
    const p=a.clone().addScaledVector(r,-7.3).addScaledVector(t,7.8);
    const pl=box(p.x,.10,p.z,7,1.25,2.2);pl.rotation.y=-theta;
  }
  // Sculptural bronze canopy: a broad curved volume rather than a wire arch.
  {
    const a=trackPoint(inTheta),r=new THREE.Vector3(Math.cos(inTheta),0,Math.sin(inTheta)),t=new THREE.Vector3(-r.z,0,r.x);
    function archSurface(drop){
      const p=[],uv=[],idx=[];
      for(let i=0;i<=150;i++)for(const d of [-1.35,1.35]){
        const ang=i/150*Math.PI,v=a.clone().addScaledVector(r,-6+d).addScaledVector(t,12*Math.cos(ang));
        v.y+=9*Math.sin(ang)+drop;p.push(v.x,v.y,v.z);uv.push(i/150*14,(d+1.35)/2.7);
      }
      for(let i=0;i<150;i++){const j=i*2;idx.push(j,j+2,j+1,j+1,j+2,j+3);}
      const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(p,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));g.setIndex(idx);g.computeVertexNormals();add(g,bronze);
    }
    archSurface(0);archSurface(-.34);
    for(const d of [-1.35,1.35]){
      const pts=[];for(let i=0;i<=150;i++){
        const ang=i/150*Math.PI,v=a.clone().addScaledVector(r,-6+d).addScaledVector(t,12*Math.cos(ang));v.y+=9*Math.sin(ang)-.30;pts.push(v);
      }
      tube(pts,.025,led,200);
    }
  }
  // Terraces follow the landscape; architecture has glazing, reveals and overhangs.
  const glass=new THREE.MeshPhysicalMaterial({color:0x55705e,metalness:.15,roughness:.11,envMapIntensity:1.8,clearcoat:1});
  for(const [x,z,w,d,rotation] of [[-53,-43,19,8,.08],[46,-47,23,8,-.12],[69,13,15,10,-.18]]){
    const base=new THREE.Group();base.position.set(x,0,z);base.rotation.y=rotation;scene.add(base);
    function block(lx,y,lz,bw,bh,bd,mat=limestone){const m=box(lx,y,lz,bw,bh,bd,mat);scene.remove(m);base.add(m);return m;}
    block(0,.1,0,w,4.4,d);block(0,4.5,0,w+1.2,.22,d+1.4);
    block(0,.4,d/2+.02,w-1.5,3.6,.045,glass);
    block(0,.4,d/2+.1,w-1.5,.07,.12,bronze);
    for(let k=0;k<8;k++)block((k/7-.5)*(w-1.6),.4,d/2+.1,.07,3.7,.14,bronze);
    for(let k=0;k<4;k++)block(0,.1,d/2+1+k*.65,w+5,.13*(4-k),.9);
  }
  // Layered garden walls, scattered stone joints and low integrated lamps.
  for(let i=0;i<26;i++){
    const angle=i/26*TAU;
    if(Math.abs(Math.sin(angle))<.17)continue;
    const x=67*Math.cos(angle),z=54*Math.sin(angle),y=.25+(i%3)*.45;
    const m=box(x,0,z,8.9,y+1.1,1.05);m.rotation.y=-angle-Math.PI/2;
    const l=box(x,y+.75,z,8.6,.025,1.07,led,.005);l.rotation.y=m.rotation.y;
  }
  // Normalize assets once, then instance genuine 3D geometry in fixed world positions.
  function parts(model){
    model.updateMatrixWorld(true);
    const bounds=new THREE.Box3().setFromObject(model),size=bounds.getSize(new THREE.Vector3()),center=bounds.getCenter(new THREE.Vector3());
    const scale=1/Math.max(.01,size.y),out=[];
    model.traverse(m=>{
      if(!m.isMesh)return;
      const g=m.geometry.clone().applyMatrix4(m.matrixWorld);
      g.translate(-center.x,-bounds.min.y,-center.z);g.scale(scale,scale,scale);
      const mat=m.material.clone();mat.transparent=false;mat.alphaTest=.4;mat.depthWrite=true;mat.side=THREE.DoubleSide;
      if(mat.isMeshStandardMaterial){mat.envMapIntensity=.75;mat.roughness=Math.max(.55,mat.roughness);}
      out.push({geometry:g,material:mat});
    });
    return out;
  }
  const unit=new THREE.Object3D(),vegetation=[];
  function scatter(name,placements){
    for(const part of parts(models[name])){
      const inst=new THREE.InstancedMesh(part.geometry,part.material,placements.length);
      placements.forEach((p,i)=>{
        unit.position.set(p.x,p.y,p.z);unit.rotation.set(p.tilt||0,p.rotation,0);unit.scale.set(p.height*(p.width||1),p.height,p.height*(p.depth||1));unit.updateMatrix();inst.setMatrixAt(i,unit.matrix);
      });
      inst.castShadow=inst.receiveShadow=true;inst.computeBoundingSphere();scene.add(inst);vegetation.push(inst);
    }
  }
  const treeA=[],treeB=[],pines=[];
  // Openings at both destinations are kept clear for the group and the camera.
  for(let i=0;i<34;i++){
    const angle=i/34*TAU+(random()-.5)*.10;
    if(Math.abs(Math.sin(angle))<.28)continue;
    const x=(67+random()*11)*Math.cos(angle),z=(53+random()*9)*Math.sin(angle);
    (i%2?treeA:treeB).push({x,y:terrainHeight(x,z),z,height:5.4+random()*5.5,rotation:random()*TAU,width:.8+random()*.3});
  }
  for(let i=0;i<12;i++){
    const angle=i/12*TAU;if(Math.abs(Math.cos(angle))>.91)continue;
    treeB.push({x:36.5*Math.cos(angle),y:.2,z:24*Math.sin(angle),height:3.4+random()*1.9,rotation:random()*TAU,width:.8});
  }
  // Fixed near trees frame both low camera destinations.
  for(const theta of [inTheta,upTheta])for(const off of [-12,13]){
    const a=trackPoint(theta),r=new THREE.Vector3(Math.cos(theta),0,Math.sin(theta)),t=new THREE.Vector3(-r.z,0,r.x),p=a.clone().addScaledVector(r,7).addScaledVector(t,off);
    treeA.push({x:p.x,y:.18,z:p.z,height:8.4+random()*2,rotation:random()*TAU,width:.8});
  }
  for(let i=0;i<22;i++){
    const a=i/22*TAU,r=95+random()*35,x=r*Math.cos(a),z=r*.83*Math.sin(a);
    pines.push({x,y:terrainHeight(x,z),z,height:9+random()*8,rotation:random()*TAU,width:.82});
  }
  scatter('tree_small_02',treeA);scatter('island_tree_01',treeB);scatter('pine_sapling_small',pines);
  const stones=[],ferns=[],grasses=[],shrubs=[];
  for(let i=0;i<220;i++){
    const a=random()*TAU,outer=i>125,rx=outer?59:37.1,rz=outer?46:24.6;
    const x=(rx+(random()-.5)*1.5)*Math.cos(a),z=(rz+(random()-.5)*1.5)*Math.sin(a);
    const p={x,y:.18,z,height:.38+random()*.65,rotation:random()*TAU,width:.8+random()*.7};
    if(i%3===0)stones.push({...p,height:.5+random()*.7});
    if(i%2===0)ferns.push({...p,height:.55+random()*.8});
    grasses.push({...p,height:.35+random()*.65});
    if(i%3===1)shrubs.push({...p,height:.7+random()*.8});
  }
  scatter('rock_09',stones);scatter('fern_02',ferns);scatter('grass_medium_01',grasses);scatter('shrub_04',shrubs);

  // Three-dimensional, clothed human meshes; these never rotate to face the camera.
  const signupPeople=[];
  function person(name,pos,height,rotation,signup=false){
    const root=models[name].clone(true);root.updateMatrixWorld(true);
    const b=new THREE.Box3().setFromObject(root),size=b.getSize(new THREE.Vector3()),center=b.getCenter(new THREE.Vector3());
    const outer=new THREE.Group();const s=height/size.y;root.scale.setScalar(s);
    root.position.set(-center.x*s,-b.min.y*s,-center.z*s);outer.add(root);outer.position.copy(pos);outer.rotation.y=rotation;
    root.traverse(m=>{if(m.isMesh){
      m.castShadow=m.receiveShadow=true;
      if(m.material){
        m.material=m.material.clone();m.material.envMapIntensity=.6;
        // Source legacy materials mark even skin and fabric as alpha-blended.
        // Opaque depth writes prevent skin from rendering over clothes.
        const masked=/ponytail|short02|eyebrow/i.test(m.material.name);
        m.material.transparent=false;m.material.depthWrite=true;
        m.material.alphaTest=masked?.45:.01;
        m.material.side=masked?THREE.DoubleSide:THREE.FrontSide;
        m.material.roughness=.72;
        if(/sportsuit|casualsuit/i.test(m.material.name))m.material.color.set(name==='coach'?0x304438:0x829887);
      }
    }});
    scene.add(outer);if(signup)signupPeople.push({name,object:outer});return outer;
  }
  const inA=trackPoint(inTheta),inT=new THREE.Vector3(-Math.sin(inTheta),0,Math.cos(inTheta));
  person('athlete',inA.clone().addScaledVector(inT,-1.2),1.78,-inTheta+Math.PI/2+.12);
  person('coach',inA.clone().addScaledVector(inT,.1),1.88,-inTheta+Math.PI/2-.10);
  person('runner',inA.clone().addScaledVector(inT,1.4),1.84,-inTheta+Math.PI/2-.3);
  const upA=trackPoint(upTheta);
  person('athlete',upA.clone().addScaledVector(new THREE.Vector3(-Math.sin(upTheta),0,Math.cos(upTheta)),-.3),1.8,-upTheta+Math.PI/2,true);
  person('coach',upA.clone(),1.88,-upTheta+Math.PI/2,true);

  // Distant photographic landscape is fixed on the horizon; all foreground is geometry.
  const skyMaterial=new THREE.ShaderMaterial({side:THREE.BackSide,depthWrite:false,toneMapped:false,
    uniforms:{panorama:{value:tex['panorama.png']},night:{value:0}},
    vertexShader:`varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
    fragmentShader:`varying vec2 vUv;uniform sampler2D panorama;uniform float night;
    void main(){float u=1.-abs(fract(vUv.x+.23)*2.-1.);float v=clamp(.565+(vUv.y-.5)*1.3,0.,1.);
    vec3 rgb=texture2D(panorama,vec2(.025+u*.95,v)).rgb;
    rgb=mix(rgb,rgb*vec3(.10,.18,.27)+vec3(.006,.009,.018),night);
    gl_FragColor=vec4(rgb,1.);#include <colorspace_fragment>}`.replace(';#include',';\n#include')});
  const sky=new THREE.Mesh(new THREE.SphereGeometry(900,64,48),skyMaterial);sky.position.y=-8;sky.renderOrder=-10;scene.add(sky);
  scene.fog=new THREE.FogExp2(0xb1b1a1,.0015);
  const sun=new THREE.DirectionalLight(0xffdb9d,3.4);sun.position.set(-82,66,-48);sun.castShadow=true;
  sun.shadow.mapSize.set(4096,4096);sun.shadow.camera.left=-100;sun.shadow.camera.right=100;
  sun.shadow.camera.top=100;sun.shadow.camera.bottom=-100;sun.shadow.camera.far=260;sun.shadow.camera.near=1;
  sun.shadow.bias=-.00015;sun.shadow.normalBias=.035;sun.shadow.radius=3;scene.add(sun);
  const hemi=new THREE.HemisphereLight(0xe4e9df,0x68553e,.55);scene.add(hemi);
  const fill=new THREE.DirectionalLight(0xb7d4d6,.25);fill.position.set(60,40,70);scene.add(fill);
  for(const theta of [inTheta,upTheta]){
    const a=trackPoint(theta);const light=new THREE.PointLight(0xffca86,12,12,2);light.position.copy(a).add(new THREE.Vector3(0,4,0));scene.add(light);
  }
  scene.updateMatrixWorld(true);
  // Merge static architectural meshes sharing materials to reduce browser draw calls.
  const batches=new Map();
  for(const m of architecture){
    if(m.parent!==scene||m.isInstancedMesh||m.material.isShaderMaterial)continue;
    if(!m.geometry.attributes.uv)continue;
    const list=batches.get(m.material)||[];list.push(m);batches.set(m.material,list);
  }
  for(const [mat,meshes]of batches){
    if(meshes.length<2)continue;
    const merged=mergeGeometries(meshes.map(m=>{
      const geometry=m.geometry.index?m.geometry.toNonIndexed():m.geometry.clone();
      return geometry.applyMatrix4(m.matrixWorld);
    }),false);
    if(!merged)continue;const combined=new THREE.Mesh(merged,mat);combined.castShadow=combined.receiveShadow=true;scene.add(combined);
    meshes.forEach(m=>scene.remove(m));
  }
  let lastTheme='',role='Athlete',lastWidth=0,lastHeight=0;
  function resize(width,height){
    if(width===lastWidth&&height===lastHeight)return;
    lastWidth=width;lastHeight=height;
    // Native canvas resolution; never stretch a 540p render into a full-HD view.
    renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.5));renderer.setSize(width,height,false);
    camera.aspect=width/height;camera.updateProjectionMatrix();
  }
  function setTheme(theme){
    if(theme===lastTheme)return;lastTheme=theme;const night=theme==='dusk'?1:0;
    skyMaterial.uniforms.night.value=night;
    sun.color.set(night?0xe1c6a2:0xffdb9d);sun.intensity=night?.18:3.4;
    hemi.color.set(night?0x9bbbd2:0xe4e9df);hemi.groundColor.set(night?0x152c26:0x68553e);hemi.intensity=night?.32:.55;
    fill.intensity=night?.25:.25;fill.color.set(night?0x5f83a5:0xb7d4d6);
    renderer.toneMappingExposure=night?.72:.95;
    scene.fog.color.set(night?0x203739:0xb1b1a1);
    led.emissiveIntensity=night?4:2.8;
    vegetation.forEach(m=>{m.material.envMapIntensity=night?.15:.75;});
    [floor,limestone,bronze,glass].forEach(m=>{m.envMapIntensity=night?.13:(m===bronze?1.15:.75);});
    water.material.uniforms.sunColor.value.set(night?0x718ba2:0xffdda0);
    renderer.shadowMap.needsUpdate=true;
  }
  function setRole(next){
    role=next;signupPeople.forEach(p=>p.object.visible=(p.name==='coach')===(role==='Coach'));
    renderer.shadowMap.needsUpdate=true;
  }
  function draw(time){
    water.material.uniforms.time.value=time*.11;
    renderer.render(scene,camera);
  }
  rig.setCamera(rig.poses.wide,0,false);setTheme('dawn');setRole('Athlete');
  renderer.shadowMap.needsUpdate=true;
  return {scene,renderer,camera,rig,draw,resize,setTheme,setRole,
    dispose(){renderer.dispose();scene.traverse(o=>{if(o.geometry)o.geometry.dispose();});}};
}
