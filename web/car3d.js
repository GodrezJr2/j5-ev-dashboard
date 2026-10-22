/* Clay J5 for the V2 Doors and Tyres pages.
   The shape is an image-to-3D mesh (Hunyuan3D-2mv, built from the clay reference renders), cleaned and
   cut into parts by tools/split_car.py: body, four doors, tailgate and four wheels, each a flat-shaded
   piece with its own hinge pivot (web/car_parts.json). Faces the cut created are a second draw group,
   painted as dark cabin so an open door shows a dark recess, not a clay block. If WebGL, the
   module or the parts file is unavailable, v2.html keeps the flat top-view diagram.

   createCar3D(host, {view: 'doors' | 'tyres', labels: ['FL','FR','RL','RR'] | null, dark: bool,
                      lockIcon: '<svg>', onFail: fn})
     .set({doors: [FL,FR,RL,RR bool open], trunk, sunroof, unlocked,
           wheels: [class x4: 'ok'|'warn'|'bad'|''], values: [text x4]})
     .dispose()
   The car faces +Z and its left side is +X. Wheel and door order is FL FR RL RR, as in v2.html. */
import * as THREE from './three.module.min.js';

const STATUS = {ok: 0x3ddc97, warn: 0xf0a93b, bad: 0xff5d5d, '': 0x7d8793};
const OPEN_TINT = [1, .60, .56];                       // multiplies the grey of an open panel
const sstep = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

const THEME = {
  dark:  {stage: 'radial-gradient(120% 95% at 50% 36%, #343c47 0%, #1b2129 62%, #141920 100%)',
          body: [.50, .49, .48], cabin: [.07, .075, .09],
          halo: .10, line: 0x8a95a3, lineA: .30, shadow: .85, sky: 0xdfe6ee, ground: 0x4b5563, key: 2.7, hemi: .95},
  light: {stage: 'radial-gradient(120% 95% at 50% 36%, #f6f7f8 0%, #e4e7ea 62%, #d9dde1 100%)',
          body: [.56, .55, .54], cabin: [.14, .15, .17],
          halo: .55, line: 0xa4abb4, lineA: .55, shadow: .30, sky: 0xffffff, ground: 0xaab1ba, key: 2.3, hemi: .95}
};

const DOOR_OPEN = .95, GATE_OPEN = 1.45;               // radians
const HINGE_X = .76;                                    // door hinge sits just inside the skin

// ---- wheel: 215/60 R17 tyre with tread blocks and a five-twin-spoke rim, built in code (the mesh's own wheels are mush) ----
const TYRE_R = .345, WHEEL_X = .80, TYRE_HW = .108;
function makeWheel(P, s){
  const clay = (k) => new THREE.MeshStandardMaterial({color: new THREE.Color().setRGB(P.body[0] * k, P.body[1] * k, P.body[2] * k), roughness: .95, flatShading: true});
  const tyreM = clay(.70), rimM = clay(.98), hubM = clay(.88);
  const dark = new THREE.MeshStandardMaterial({color: new THREE.Color().setRGB(P.cabin[0], P.cabin[1], P.cabin[2]), roughness: 1, flatShading: true});
  const g = new THREE.Group();
  const lathe = (pts, seg, m) => { const geo = new THREE.LatheGeometry(pts.map(p => new THREE.Vector2(p[0], p[1])), seg); geo.rotateZ(-Math.PI / 2); return new THREE.Mesh(geo, m); };
  // road tyre: slick flat tread, rounded shoulders, gently bulging sidewall, 40 facets round
  g.add(lathe([[.205, -TYRE_HW + .004], [.250, -TYRE_HW - .002], [.300, -.110], [.330, -.092], [.341, -.068], [TYRE_R, -.044],
               [TYRE_R, .044], [.341, .068], [.330, .092], [.300, .110], [.250, TYRE_HW + .002], [.205, TYRE_HW - .004]], 40, tyreM));
  // rim: recessed dark barrel, lip, five pairs of spokes, hub with bolts
  const barrel = new THREE.Mesh(new THREE.CylinderGeometry(.215, .215, .022, 26), dark); barrel.rotation.z = Math.PI / 2; barrel.position.x = .082; g.add(barrel);
  const lip = new THREE.Mesh(new THREE.TorusGeometry(.212, .013, 5, 26), rimM); lip.rotation.y = Math.PI / 2; lip.position.x = .103; g.add(lip);
  const spokeGeo = new THREE.BoxGeometry(.024, .150, .040);
  for(let k = 0; k < 5; k++) for(const d of [-1, 1]){
    const arm = new THREE.Group(); arm.rotation.x = k / 5 * Math.PI * 2 + d * .15;
    const sp = new THREE.Mesh(spokeGeo, rimM); sp.position.set(.094 - (d > 0 ? .004 : 0), .125, d * .004); sp.rotation.x = d * .10; arm.add(sp); g.add(arm);
  }
  const hub = new THREE.Mesh(new THREE.CylinderGeometry(.062, .068, .030, 18), hubM); hub.rotation.z = Math.PI / 2; hub.position.x = .104; g.add(hub);
  const boltGeo = new THREE.CylinderGeometry(.011, .011, .014, 6);
  for(let k = 0; k < 5; k++){ const a = k / 5 * Math.PI * 2 + .3;
    const b = new THREE.Mesh(boltGeo, rimM); b.rotation.z = Math.PI / 2; b.position.set(.121, Math.cos(a) * .038, Math.sin(a) * .038); g.add(b); }
  g.traverse(o => { if(o.isMesh) o.castShadow = o.receiveShadow = true; });
  g.scale.x = s;
  return g;
}

function roundRect(w, h, r){
  const x = -w / 2, y = -h / 2, sh = new THREE.Shape();
  sh.moveTo(x + r, y); sh.lineTo(x + w - r, y); sh.quadraticCurveTo(x + w, y, x + w, y + r); sh.lineTo(x + w, y + h - r);
  sh.quadraticCurveTo(x + w, y + h, x + w - r, y + h); sh.lineTo(x + r, y + h); sh.quadraticCurveTo(x, y + h, x, y + h - r);
  sh.lineTo(x, y + r); sh.quadraticCurveTo(x, y, x + r, y); return sh;
}

// ---- cabin furniture, low-poly clay like the rest: seats, dash, console, wheel. Only seen through an open door or the hatch ----
function makeInterior(P, wheelZ){
  const k = .50, m = new THREE.MeshStandardMaterial({color: new THREE.Color().setRGB(P.body[0] * k, P.body[1] * k, P.body[2] * k), roughness: 1, flatShading: true});
  const g = new THREE.Group(), box = (w, h, d, x, y, z, rx) => { const o = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m); o.position.set(x, y, z); if(rx) o.rotation.x = rx; o.castShadow = o.receiveShadow = true; g.add(o); return o; };
  const seat = (x, z, w) => { box(w, .13, .50, x, .54, z);                       // cushion
    box(w, .58, .12, x, .92, z - .30, -.16);                                       // backrest, leaning back
    box(w * .52, .17, .09, x, 1.30, z - .37, -.16); };                              // headrest
  seat(-.34, .30, .46); seat(.34, .30, .46);                                       // front pair
  seat(-.37, -.78, .34); seat(0, -.78, .34); seat(.37, -.78, .34);               // rear bench
  box(1.12, .20, .26, 0, .86, .74, .25);                                            // dash
  box(.18, .24, .86, 0, .58, -.02);                                                 // centre console
  const wheel = new THREE.Mesh(new THREE.TorusGeometry(.16, .022, 5, 18), m); wheel.position.set(-.34, 1.0, .50); wheel.rotation.x = 1.0; g.add(wheel);   // right-hand drive
  box(.04, .04, .20, -.34, .93, .60, .25);                                          // column
  return g;
}

// ---- the parts file, fetched once and shared by every car on the page ----------------------------
let PARTS = null;
const b64 = s => { const b = atob(s), u = new Uint8Array(b.length); for(let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u.buffer; };
function loadParts(){
  if(PARTS) return PARTS;
  return PARTS = fetch(new URL('./car_parts.json', import.meta.url).href, {cache: 'no-cache'})   // unversioned file: always revalidate
    .then(r => { if(!r.ok) throw new Error('parts'); return r.json(); })
    .then(meta => {
      const out = {wheelZ: meta.wheelZ, wheelY: meta.wheelY};
      meta.parts.forEach(p => {
        const q = new Int16Array(b64(p.pos)), pos = new Float32Array(q.length);
        for(let i = 0; i < q.length; i++) pos[i] = q[i] / meta.q;
        out[p.name] = {pivot: p.pivot, pos, nskin: p.nskin, ao: new Uint8Array(b64(p.ao)),
          idx: p.idx32 ? new Uint32Array(b64(p.idx)) : new Uint16Array(b64(p.idx))};
      });
      return out;
    }).catch(e => { PARTS = null; throw e; });
}

// geometry for one part: indexed, flat-shaded in the viewer. Skin faces come first (group 0, clay darkened
// low on the body and under the arches); faces the cut made come last (group 1, dark cabin).
function partGeometry(p, P){
  const n = p.pos.length / 3, col = new Float32Array(n * 3), py = p.pivot[1];
  for(let i = 0; i < n; i++){
    const ao = (.70 + .30 * sstep(.22, .85, p.pos[i * 3 + 1] + py)) * (.4 + .8 * p.ao[i] / 255);   // lower body is darker, creases darker still
    col[i * 3] = P.body[0] * ao; col[i * 3 + 1] = P.body[1] * ao; col[i * 3 + 2] = P.body[2] * ao;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(p.pos, 3));
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  g.setIndex(new THREE.BufferAttribute(p.idx, 1));
  g.addGroup(0, p.nskin, 0);
  if(p.idx.length > p.nskin) g.addGroup(p.nskin, p.idx.length - p.nskin, 1);
  return g;
}

export function createCar3D(host, opts){
  opts = opts || {};
  const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true, powerPreference: 'low-power'});
  if(!renderer.getContext()) throw new Error('no webgl');
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 0);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const cv = renderer.domElement;
  cv.className = 'c3d'; cv.style.touchAction = 'pan-y';
  const P = opts.dark !== false ? THEME.dark : THEME.light;
  host.style.background = P.stage;
  host.appendChild(cv);

  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(P.sky, P.ground, P.hemi));
  const key = new THREE.DirectionalLight(0xffffff, P.key); key.position.set(3.2, 7, 4.2); scene.add(key);
  key.castShadow = true; key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -.0004; key.shadow.normalBias = .02; key.shadow.radius = 3;
  Object.assign(key.shadow.camera, {left: -3.4, right: 3.4, top: 3.4, bottom: -3.4, near: 1, far: 20}); key.shadow.camera.updateProjectionMatrix();
  const fill = new THREE.DirectionalLight(0xdfe8ff, .55); fill.position.set(-5, 3, -4); scene.add(fill);

  const mat = () => new THREE.MeshStandardMaterial({vertexColors: true, roughness: .95, metalness: 0, flatShading: true});
  const cabinMat = new THREE.MeshStandardMaterial({color: new THREE.Color().setRGB(P.cabin[0], P.cabin[1], P.cabin[2]),
    roughness: 1, flatShading: true, side: THREE.DoubleSide});
  const car = new THREE.Group(); scene.add(car);

  // filled in once the parts arrive; frame() and set() work on empty kits meanwhile
  const kit = {doors: [], gate: null, gateMat: null, wheels: [], sun: null, sunHole: null};
  const WX = [1, -1, 1, -1];
  const labelPos = [new THREE.Vector3(1.55, .34, 1.36), new THREE.Vector3(-1.55, .34, 1.36),
                    new THREE.Vector3(1.55, .34, -1.30), new THREE.Vector3(-1.55, .34, -1.30)];
  const gateS = {cur: 0, to: 0}, sunS = {cur: 0, to: 0};
  let pending = null, loaded = false;

  function build(D){
    const piece = (name) => { const p = D[name], m = mat(), mesh = new THREE.Mesh(partGeometry(p, P), [m, cabinMat]);
      mesh.castShadow = mesh.receiveShadow = true;
      const g = new THREE.Group(); g.position.set(p.pivot[0], p.pivot[1], p.pivot[2]); g.add(mesh); return {g, m, p}; };
    const b = piece('body'); car.add(b.g);
    D.wheelZ.forEach((z, e) => { labelPos[e * 2].z = z; labelPos[e * 2 + 1].z = z; });

    for(let i = 0; i < 4; i++){
      const s = i % 2 === 0 ? 1 : -1, d = piece('door' + i);
      // swing about the hinge line: pivot x is moved in from the car centre line to just inside the skin
      d.g.position.x = s * HINGE_X;
      d.g.children[0].position.x = -s * HINGE_X;
      car.add(d.g);
      kit.doors.push({grp: d.g, mat: d.m, cur: 0, to: 0, max: -s * DOOR_OPEN});
    }
    car.add(makeInterior(P, D.wheelZ));
    const gt = piece('gate'); car.add(gt.g); kit.gate = gt.g; kit.gateMat = gt.m;

    // panoramic roof panel: cut from the roof, slides back over it; the dark recess is the cut's own faces
    const sn = piece('sun'); car.add(sn.g); kit.sun = sn.g; kit.sunBase = D.sun.pivot[1]; kit.sunHole = {visible: false};

    // wheels are built in code; the status ring sits on the rim face
    for(let i = 0; i < 4; i++){
      const s = WX[i], w = makeWheel(P, s);
      w.position.set(s * WHEEL_X, TYRE_R, D.wheelZ[i >> 1]);
      car.add(w);
      const ringMat = new THREE.MeshBasicMaterial({color: STATUS[''], side: THREE.DoubleSide, transparent: true, opacity: .92});
      const ring = new THREE.Mesh(new THREE.RingGeometry(.222, .262, 44), ringMat);
      ring.rotation.y = s * Math.PI / 2; ring.position.set(s * (WHEEL_X + TYRE_HW + .004), TYRE_R, D.wheelZ[i >> 1]);
      car.add(ring);
      // a glowing plate on the ground under the tyre: readable from above, where the rim face is edge-on
      const plateMat = new THREE.MeshBasicMaterial({color: STATUS[''], transparent: true, opacity: .30, depthWrite: false});
      const plate = new THREE.Group(); plate.position.set(s * WHEEL_X, .016, D.wheelZ[i >> 1]); plate.rotation.x = -Math.PI / 2;
      plate.add(new THREE.Mesh(new THREE.ShapeGeometry(roundRect(.40, .92, .10)), plateMat));
      const edgeMat = new THREE.LineBasicMaterial({color: STATUS[''], transparent: true, opacity: .9});
      plate.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(roundRect(.40, .92, .10).getPoints(8)), edgeMat));
      car.add(plate);
      ring.visible = plate.visible = false;
      kit.wheels.push({ringMat, ring, plate, plateMat, edgeMat, st: ''});
    }
    loaded = true;
    if(pending) apply(pending);
  }
  loadParts().then(build).catch(e => { console.error('car3d', e); if(opts.onFail) opts.onFail(); });

  // ---- stage: halo disc, lane lines, soft contact shadow -----------------------------------
  const haloMat = new THREE.MeshBasicMaterial({color: 0xffffff, transparent: true, opacity: P.halo, depthWrite: false});
  const halo = new THREE.Mesh(new THREE.CircleGeometry(3.0, 64), haloMat);
  halo.rotation.x = -Math.PI / 2; halo.position.y = .004; scene.add(halo);
  const haloRingMat = new THREE.MeshBasicMaterial({color: STATUS.ok, transparent: true, opacity: .75, depthWrite: false});
  const haloRing = new THREE.Mesh(new THREE.RingGeometry(2.96, 3.02, 96), haloRingMat);
  haloRing.rotation.x = -Math.PI / 2; haloRing.position.y = .006; scene.add(haloRing);

  const fadeCv = document.createElement('canvas'); fadeCv.width = 4; fadeCv.height = 256;
  const fx = fadeCv.getContext('2d'), fg = fx.createLinearGradient(0, 0, 0, 256);
  fg.addColorStop(0, 'rgba(255,255,255,0)'); fg.addColorStop(.35, 'rgba(255,255,255,1)');
  fg.addColorStop(.65, 'rgba(255,255,255,1)'); fg.addColorStop(1, 'rgba(255,255,255,0)');
  fx.fillStyle = fg; fx.fillRect(0, 0, 4, 256);
  const fadeTex = new THREE.CanvasTexture(fadeCv);
  const lineMat = new THREE.MeshBasicMaterial({color: P.line, transparent: true, opacity: P.lineA, map: fadeTex, depthWrite: false});
  [-4.2, -3.4, 3.4, 4.2].forEach((x, k) => {
    const l = new THREE.Mesh(new THREE.PlaneGeometry(k === 0 || k === 3 ? .05 : .035, 30), lineMat);
    l.rotation.x = -Math.PI / 2; l.position.set(x, .003, 0); scene.add(l);
  });

  const sc = document.createElement('canvas'); sc.width = sc.height = 128;
  const sx = sc.getContext('2d'), gr = sx.createRadialGradient(64, 64, 4, 64, 64, 62);
  gr.addColorStop(0, 'rgba(0,0,0,.80)'); gr.addColorStop(.5, 'rgba(0,0,0,.34)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
  sx.fillStyle = gr; sx.fillRect(0, 0, 128, 128);
  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(5.4, 2.9),
    new THREE.MeshBasicMaterial({map: new THREE.CanvasTexture(sc), transparent: true, depthWrite: false, opacity: P.shadow}));
  shadow.rotation.x = -Math.PI / 2; shadow.position.y = .008; scene.add(shadow);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(9, 9), new THREE.ShadowMaterial({opacity: P.shadow * .55}));   // the key light's real shadow
  floor.rotation.x = -Math.PI / 2; floor.position.y = .01; floor.receiveShadow = true; scene.add(floor);

  // ---- DOM overlays: wheel labels and lock badge ----------------------------------------------
  const labels = [];
  if(opts.labels) for(let i = 0; i < 4; i++){
    const d = document.createElement('div'); d.className = 'c3l';
    d.innerHTML = '<b>' + opts.labels[i] + '</b><span></span>';
    host.appendChild(d); labels.push(d);
  }
  const lockEl = document.createElement('div'); lockEl.className = 'c3lock'; host.appendChild(lockEl);

  // ---- camera, drag-to-turn, idle sway ----------------------------------------------------------
  const camera = new THREE.PerspectiveCamera(28, 1, .1, 80);
  const reduced = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const tyres = opts.view === 'tyres';
  const dbgPitch = /c3pitch=(-?[\d.]+)/.exec(location.search);
  const dbgDist = /c3dist=([\d.]+)/.exec(location.search), dbgAt = /c3at=(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)/.exec(location.search);
  const pitch = dbgPitch ? +dbgPitch[1] : tyres ? .95 : .42, dist = dbgDist ? +dbgDist[1] : tyres ? 11.6 : 10.2, yaw0 = tyres ? .55 : .62;
  const dbgYaw = /c3yaw=(-?[\d.]+)/.exec(location.search);           // ?c3yaw=1.57 freezes the camera at that angle (debugging)
  const dbgOpen = /c3open=([\d,]*)/.exec(location.search);           // ?c3open=0,1,5 opens door 0, door 1, gate (4) or roof (5)
  let yaw = dbgYaw ? +dbgYaw[1] : yaw0, vel = 0, touched = !!dbgYaw, down = false, lastX = 0, sway = 0;
  cv.addEventListener('pointerdown', e => { down = true; touched = true; lastX = e.clientX; vel = 0;
    try{ cv.setPointerCapture(e.pointerId); }catch(_){} });
  cv.addEventListener('pointermove', e => { if(!down) return;
    const dx = e.clientX - lastX; lastX = e.clientX; yaw -= dx * .011; vel = -dx * .011; });
  const up = () => { down = false; };
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);

  function resize(){
    const w = host.clientWidth || 360, h = host.clientHeight || Math.round(w * .8);
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize); ro.observe(host); resize();

  const tmp = new THREE.Vector3();
  let visible = true, alive = true, last = performance.now(), raf = 0, first = true;
  const io = new IntersectionObserver(es => { visible = es[0].isIntersecting; }, {threshold: 0});
  io.observe(host);

  const tint = (m, k) => m.color.setRGB(1 + (OPEN_TINT[0] - 1) * k, 1 + (OPEN_TINT[1] - 1) * k, 1 + (OPEN_TINT[2] - 1) * k);

  const dbg = !!(dbgYaw || dbgOpen);                                  // debug URLs keep rendering in a background tab, on a timer
  const next = () => dbg ? setTimeout(() => frame(performance.now()), 100) : requestAnimationFrame(frame);
  function frame(now){
    raf = next();
    if(!alive || !visible || (document.hidden && !dbg)){ last = now; return; }
    const dt = Math.min(.05, (now - last) / 1000); last = now;
    if(!touched && !reduced){ sway += dt; yaw = yaw0 + Math.sin(sway * .55) * .62; }
    else if(!down){ yaw += vel; vel *= .93; }
    camera.position.set(Math.sin(yaw) * Math.cos(pitch) * dist, Math.sin(pitch) * dist + .5,
      Math.cos(yaw) * Math.cos(pitch) * dist);
    if(dbgAt){ camera.position.x += +dbgAt[1]; camera.position.y += +dbgAt[2] - .78; camera.position.z += +dbgAt[3]; }
    if(dbgAt) camera.lookAt(+dbgAt[1], +dbgAt[2], +dbgAt[3]); else camera.lookAt(0, .78, -.1);

    const k = reduced ? 1 : 1 - Math.pow(.0009, dt);
    kit.doors.forEach(d => { d.cur += (d.to - d.cur) * k; d.grp.rotation.y = d.cur * d.max; tint(d.mat, Math.min(1, d.cur)); });
    if(kit.gate){
      gateS.cur += (gateS.to - gateS.cur) * k; kit.gate.rotation.x = gateS.cur * GATE_OPEN; tint(kit.gateMat, Math.min(1, gateS.cur));
      sunS.cur += (sunS.to - sunS.cur) * k; kit.sun.position.z = -.60 - sunS.cur * .78; kit.sun.position.y = kit.sunBase + sunS.cur * .035;
    }

    if(!reduced) kit.wheels.forEach(w => { if(w.st === 'bad') w.plateMat.opacity = .26 + .16 * Math.sin(now * .004); else w.plateMat.opacity = .30; });
    renderer.render(scene, camera);
    if(labels.length){
      const w = host.clientWidth, h = host.clientHeight;
      labelPos.forEach((p, i) => {
        tmp.copy(p).project(camera);
        labels[i].style.transform = 'translate(' + ((tmp.x * .5 + .5) * w).toFixed(1) + 'px,' +
          ((-tmp.y * .5 + .5) * h).toFixed(1) + 'px) translate(-50%,-50%)';
        labels[i].style.opacity = tyres || WX[i] * camera.position.x > .6 ? 1 : 0;       // from above all four show; low down the far side hides behind the body
      });
    }
    if(first && loaded){ first = false; host.classList.add('ready'); }
  }
  raf = next();

  function apply(s){
    s = s || {};
    (s.doors || []).forEach((o, i) => { if(kit.doors[i]) kit.doors[i].to = o ? 1 : 0; });
    gateS.to = s.trunk ? 1 : 0;
    sunS.to = s.sunroof ? 1 : 0;
    if(dbgOpen){ const o = dbgOpen[1].split(',').map(Number);
      kit.doors.forEach((d, i) => { if(o.includes(i)) d.to = 1; });
      if(o.includes(4)) gateS.to = 1; if(o.includes(5)) sunS.to = 1; }
    kit.wheels.forEach(w => { w.ring.visible = w.plate.visible = !!s.wheels; });          // status only where wheel data is shown
    if(s.wheels) for(let i = 0; i < 4; i++){ const w = kit.wheels[i]; if(!w) continue;
      w.st = s.wheels[i] != null ? s.wheels[i] : ''; const hex = STATUS[w.st] || STATUS[''];
      w.ringMat.color.setHex(hex); w.plateMat.color.setHex(hex); w.edgeMat.color.setHex(hex); }
    const anyOpen = (s.doors || []).some(Boolean) || s.trunk || s.sunroof;
    haloRingMat.color.setHex(anyOpen ? STATUS.bad : s.unlocked ? STATUS.warn : STATUS.ok);
    labels.forEach((el, i) => {
      const v = s.values && s.values[i]; el.lastChild.textContent = v || '';
      const c = s.wheels && s.wheels[i]; el.className = 'c3l' + (c ? ' ' + c : '');
    });
    lockEl.className = 'c3lock' + (s.unlocked ? ' un' : '');
    lockEl.innerHTML = (opts.lockIcon || '') + '<span>' + (s.unlocked ? 'Unlocked' : 'Locked') + '</span>';
    lockEl.hidden = s.unlocked == null;
  }

  return {
    set(s){ pending = s; apply(s); },
    dispose(){
      alive = false; cancelAnimationFrame(raf); clearTimeout(raf); ro.disconnect(); io.disconnect();
      scene.traverse(o => { if(o.geometry) o.geometry.dispose();
        if(o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => { if(m.map) m.map.dispose(); m.dispose(); }); });
      renderer.dispose(); renderer.forceContextLoss();
      cv.remove(); labels.forEach(l => l.remove()); lockEl.remove();
    }
  };
}
