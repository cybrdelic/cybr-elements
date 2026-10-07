import {PowerContacts} from './power-contacts.js?v=studio-rc-37-audit';
import {projectionMeasureShader} from './projection-measure.js?v=studio-rc-37-audit';
import {GeometryPressure} from './pressure-geometry.js?v=studio-rc-37-audit';
import {gpuCosts} from './gpu-costs.js?v=studio-rc-37-audit';
import {pruneShaderFunctions} from '../shader-specialization.js?v=studio-rc-37-audit';
import {conservativeFluxShader} from './conservative-transport.js?v=studio-rc-37-audit';
import {flowDetailShader,flowDetailVelocity} from './flow-detail.js?v=studio-rc-37-audit';
import {reactionPrecisionShader} from './reaction-precision.js?v=studio-rc-37-audit';
import {fusedFluxReactionShader} from './fused-transport.js?v=studio-rc-37-audit';
import {
  surfaceWGSL,
  basicSurfaceWGSL,
  damageResetWGSL,
  FIRE_COLORS,
} from './objects.js?v=studio-rc-37-audit';
import { ForestMesh } from './forest-mesh.js?v=studio-rc-37-audit';
import {WoodStructure} from '../wood-structure.js?v=studio-rc-37-audit';
import {WoodCollision} from './wood-collision.js?v=studio-rc-37-audit';
import {WoodFlux,WOOD_GAS_PILOT,woodPacketFraction} from './wood-flux.js?v=studio-rc-37-audit';
import { emberComputeWGSL, emberRenderWGSL } from './embers.js?v=studio-rc-37-audit';
import { probeGPU, gpuSessionTimeout } from './gpu-session.js?v=studio-rc-37-audit';
import { simulationShaders, pressureShaders } from './shaders.js?v=studio-rc-37-audit';
import {CompressibleShockStage,shockFlowTransferWeight} from './shock-euler.js?v=studio-rc-37-audit';
import { rendererShaders, dilateWGSL, dilateReceiversWGSL, ROOM_SIZE } from './renderer.js?v=studio-rc-37-audit';
import { adaptiveFlowShaders, initialAdaptiveFlowCommands, ADAPTIVE_FLOW_COMMAND_BYTES, ADAPTIVE_FLOW_OFFSETS } from './adaptive-flow.js?v=studio-rc-37-audit';
import { AdaptivePressure } from './adaptive-pressure.js?v=studio-rc-37-audit';
import { createLightingWork, lightingWorkShaders, recordLightingWork, createLightingReceivers } from './lighting-work.js?v=studio-rc-37-audit';
import { createBrickPool, brickPoolScalarShaders,brickPoolVelocityShader, POOL_INDIRECT } from './brick-pool.js?v=studio-rc-37-audit';
import { pooledChemistryConsumer } from './pooled-coupling.js?v=studio-rc-37-audit';
import { FuelBrush } from '../fuel-ground.js?v=studio-rc-37-audit';
import { advanceSmokeDecay } from '../smoke-lifecycle.js?v=studio-rc-37-audit';
import {powerDirection as authoredPowerDirection, powerDefinition, POWER_DEFINITIONS} from '../fire-powers.js?v=studio-rc-37-audit';
import {PowerCastPool} from '../fire-abilities.js?v=studio-rc-37-audit';
import { FLOOR_FUEL_SIZE, floorFuelUpdateWGSL, floorFuelClearWGSL, floorWoodWearClearWGSL, floorDepositsClearWGSL, expandFuelDeposits } from './floor-fuel.js?v=studio-rc-37-audit';
export function cflSafeSpeed(maxSpeed, telemetryLag, burstAge) {
  if (burstAge < 0.12) return Math.max(maxSpeed, 12);
  // Even a current readback describes the completed interval. Reserve one
  // further interval for the frame we are about to simulate, plus map lag.
  const lag = Math.max(0, Math.min(telemetryLag, 8)) + 1;
  // A few late readbacks do not imply a new explosion. Bound ordinary velocity
  // growth from the last observed field instead of jumping straight to 12.
  const predicted = Math.max(maxSpeed * (1 + 0.05 * lag), maxSpeed + 0.35 * lag);
  return telemetryLag > 8 ? Math.max(predicted, 12) : predicted;
}
// A finite startup safety margin covers new wood source-volume flow before
// asynchronous velocity telemetry has observed it. This only chooses dt;
// it never clips physical velocity or disables the current invalid-state gate.
export function woodIgnitionSpeedFloor(structured,active,age,tree=false){
  const duration=tree?WOOD_GAS_PILOT.treeDurationS:WOOD_GAS_PILOT.durationS;
  return structured&&active&&age>=0&&age<duration+.5?12:0;
}
export function shouldRefreshLighting(dt,ready,frameNumber,lastLightingCostMs,{age,transient=false,moved=false}={}){
 if(!ready||moved)return true;
 if(dt<=0)return false;
 if(Number.isFinite(age))return transient||age>=1/30-1e-8;
 // Compatibility for isolated harness callers; live scheduling passes age.
 const stride=Number.isFinite(lastLightingCostMs)&&lastLightingCostMs<4?1:2;
 return stride===1||frameNumber%stride===0;
}

export class PyroSolver {
  static async create(canvas, options = {}) {
    const { adapter, context, format } = await probeGPU(canvas);
    const features = ['timestamp-query','subgroups'].filter(feature=>adapter.features.has(feature));
    const device = await gpuSessionTimeout(adapter.requestDevice({ requiredFeatures: features }), 'device request');
    let s;
    try {
      s = new PyroSolver(device, canvas, { ...options, context, format });
    } catch (e) {
      device.destroy();
      throw e;
    }
    s.adapter = {
      ...adapter.info.toJSON?.(),
      vendor: adapter.info.vendor,
      architecture: adapter.info.architecture,
      device: adapter.info.device,
      description: adapter.info.description,
    };
    try {
      await gpuSessionTimeout(s.init(), 'solver startup');
      return s;
    } catch (e) {
      s.destroy();
      throw e;
    }
  }
  constructor(device, canvas, { N = 128, D = 256, context, format, adaptive = false, pressureWork = false, brickPool = false, poolCapacity = 1024, sharedChemistry = brickPool, phaseLighting = false, flowDetail = false, reactionPrecision = false, fuseFinalFlux = false, fluxBlock = [4,4,4], lightWork = false, lightReceivers = false, transport = "maccormack", hasPowers = true, powerKind = null, multirateWood = false, pressureCache = false } = {}) {
    this.device = device;
    this.canvas = canvas;
    if(!["maccormack","flux"].includes(transport))throw Error("Unknown transport");
    this.transport=transport;
    this.hasPowers=hasPowers;
    this.powerKind=powerKind;
    this.sourcePipelineCache=new Map();
    this.multirateWood=multirateWood;this.usePressureCache=pressureCache;
    if(multirateWood&&adaptive)throw Error("Multirate wood requires the global flow path");
    this.N = N;
    this.D = D;
    this.adaptive = adaptive;
    this.pressureWork = pressureWork;
    this.useBrickPool = brickPool;
    this.useLightWork = lightWork;
    this.useLightReceivers = lightReceivers && !lightWork;
    this.poolCapacity = sharedChemistry?4096:poolCapacity;
    this.sharedChemistry=sharedChemistry;
    this.phaseLighting=phaseLighting;
    this.flowDetail=flowDetail;
    this.reactionPrecision=reactionPrecision;
    this.fluxBlock=[...fluxBlock];
    this.fuseFinalFlux=fuseFinalFlux;
    if(fuseFinalFlux&&(transport!=='flux'||fluxBlock.some(v=>v!==4)))throw Error('Final flux fusion needs conservative 4³ transport');
    if(brickPool&&fluxBlock.some(v=>v!==4))throw Error('Alternate flux workgroups require dense storage');
    this.time = 0;
    this.smokeDecayRemainder = 0;
    this.burstAge = 0;
    this.maxSpeed = 12;
    this.source = [0, 0.58, 0];
    this.smoke = true;
    this.seed = 2;
    this.active = true;
    this.fuel = 0;
    this.effect = [0, 1, 0.085, 0];
    this.powerDirection = authoredPowerDirection();
    this.powerStrength = 1;
    this.launchPowerDirection = null;
    this.launchPowerStrength = null;
    this.powerTrailLast = null;
    this.powerCasts = new PowerCastPool();
    this.shockStage=null;this.shockInitPromise=null;this.shockRemaining=0;
    this.simulationParams = new Float32Array(96);
    this.dynamics = [1, 1, 1, 1];
    this.chemistry = [1, 1, 1, 1];
    this.objectId = null;
    this.color = 'natural';
    this.embers = true;
    this.fuelBrush = new FuelBrush();
    this.hasFloorFuel = false;
    this.floorIgnition = false;
    this.floorIndex = 0;
    this.si = 0;
    this.errors = [];
    this.stateEpoch = 0;
    this.destroyed = false;
    device.addEventListener('uncapturederror', (e) => {
      this.errors.push(e.error.message);
      console.error(e.error.message);
    });
    device.lost.then((info) => {
      this.lost = info.message || info.reason;
    });
    this.context = context;
    this.format = format;
    this.context.configure({ device, format: this.format, alphaMode: 'opaque' });
    this.resources = [];
    this.pipelines = {};
    this.cache = new Map();
    this.ids = new WeakMap();
    this.nextId = 0;
    this.textureId = 0;
  }
  texture(n, format = 'rgba16float') {
    const t = this.device.createTexture({
      size: [n, n, n],
      dimension: '3d',
      format,
      usage:
        GPUTextureUsage.TEXTURE_BINDING |
        GPUTextureUsage.STORAGE_BINDING |
        GPUTextureUsage.COPY_DST,
    });
    const out = { t, view: t.createView(), n, id: ++this.textureId };
    this.resources.push(t);
    return out;
  }
  async pipeline(code, label, entryPoint = 'main') {
    const module = this.device.createShaderModule({ code, label });
    const info = await module.getCompilationInfo();
    const errors = info.messages.filter((m) => m.type === 'error');
    if (errors.length)
      throw Error(label + ': ' + errors.map((m) => m.lineNum + ': ' + m.message).join('\n'));
    return this.device.createComputePipelineAsync({
      layout: 'auto',
      compute: { module, entryPoint },
      label,
    });
  }
  async init() {
    const d = this.device;
    this.sampler = d.createSampler({
      minFilter: 'linear',
      magFilter: 'linear',
      addressModeU: 'clamp-to-edge',
      addressModeV: 'clamp-to-edge',
      addressModeW: 'clamp-to-edge',
    });
    this.params = Array.from({ length: 12 }, () =>
      d.createBuffer({ size: 1536, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST }),
    );
    if(this.multirateWood){
      this.woodParams=d.createBuffer({label:'wood-frame-params',size:384,usage:GPUBufferUsage.UNIFORM|GPUBufferUsage.COPY_DST});
      this.woodPacket=d.createBuffer({label:'wood-frame-packet-fraction',size:16,usage:GPUBufferUsage.UNIFORM|GPUBufferUsage.COPY_DST});
      this.resources.push(this.woodParams,this.woodPacket);
      this.device.queue.writeBuffer(this.woodPacket,0,new Float32Array([1,1/60,0,0]));
    }
    this.emptyShockRM=d.createBuffer({label:'inactive-compressible-shock-binding',size:16,usage:GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_DST});this.resources.push(this.emptyShockRM);
    this.view = d.createBuffer({
      size: 192,
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    });
    this.stats = d.createBuffer({
      size: 16,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST,
    });
    this.groupStats = d.createBuffer({
      size: Math.ceil((this.N + 1) / 4) ** 3 * 16,
      usage: GPUBufferUsage.STORAGE,
    });
    // Readbacks must never hold the presentation loop on mapAsync. Keep a
    // small ring so a slow browser/driver mapping cannot freeze every frame.
    this.telemetrySlots = Array.from({ length: 3 }, () => ({
      stats: d.createBuffer({ size: this.adaptive?32:16, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ }),
      pending: false,
      queryPending: false,
    }));
    this.latestTelemetry = {
      maxSpeed: this.maxSpeed,
      preDivergence: 0,
      postDivergence: 0,
      gpu: null,
    };
    this.lastLightingCostMs = null;
    this.frameNumber = 0;
    this.completedFrames = 0;
    this.inFlight = [];
    this.masks = [0, 1].map(() =>
      d.createBuffer({
        size: (this.D / 8) ** 3 * 4,
        usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
      }),
    );
    // Transport keeps oxygen/cold fuel. The optical mask follows chemistry
    // ping-pong separately so invisible state cannot fill the lighting mask.
    this.opticalMasks = [0, 1].map(() =>
      d.createBuffer({
        size: (this.D / 8) ** 3 * 4,
        usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
      }),
    );
    this.bricks = d.createBuffer({ size: (this.D / 8) ** 3 * 16 + this.D**3*4, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST });
    this.indirect = d.createBuffer({
      size: 12,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.INDIRECT | GPUBufferUsage.COPY_DST | GPUBufferUsage.COPY_SRC,
    });
    this.reactionOffset=(this.D/8)**3*16;this.reactionLedger=this.bricks;
    d.queue.writeBuffer(this.indirect, 0, new Uint32Array([0, 2, 4]));
    this.v = Array.from({ length: 3 }, () => this.texture(this.N + 1));
    this.c = this.useBrickPool&&this.sharedChemistry?null:Array.from({ length: 3 }, () => this.texture(this.D));
    if(this.transport==='flux'){
      this.fluxIndirect=d.createBuffer({size:12,usage:GPUBufferUsage.INDIRECT|GPUBufferUsage.COPY_DST});
      d.queue.writeBuffer(this.fluxIndirect,0,new Uint32Array([0,8/this.fluxBlock[0],64/(this.fluxBlock[1]*this.fluxBlock[2])]));
      this.fluxUpload=new ArrayBuffer(16);
      this.fluxUploadFloats=new Float32Array(this.fluxUpload);
      this.fluxParams=Array.from({length:12},()=>d.createBuffer({size:16,usage:GPUBufferUsage.UNIFORM|GPUBufferUsage.COPY_DST}));
      this.fluxDiagnostics=d.createBuffer({size:16,usage:GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_SRC|GPUBufferUsage.COPY_DST});
      for(const slot of this.telemetrySlots){slot.fluxStatus=d.createBuffer({size:16,usage:GPUBufferUsage.MAP_READ|GPUBufferUsage.COPY_DST});slot.fluxPending=false;}
    }
    if (this.useBrickPool) this.chemistryPool = await createBrickPool(d, {
      D:this.D, capacity:this.poolCapacity, sharedStorage:this.sharedChemistry, denseOccupancy:this.sharedChemistry ? .25 : .5, maxTextureDimension3D:d.limits.maxTextureDimension3D,
    });
    if(this.sharedChemistry&&this.chemistryPool)this.c=this.chemistryPool.fields.map(field=>({t:field.texture,view:field.view,n:this.D}));
    if (this.chemistryPool) for (const slot of this.telemetrySlots) {
      slot.poolStatus = d.createBuffer({size:64,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
      slot.poolPending = false;
    }
    if(this.usePressureCache){
      this.pressureSource=this.texture(this.D/2,'r32float');
      this.pressureSourceClear=await this.pipeline(`@group(0) @binding(0) var dst:texture_storage_3d<r32float,write>;
@compute @workgroup_size(4,4,4) fn main(@builtin(global_invocation_id) i:vec3u){if(any(i>=vec3u(${this.D/2}))){return;}textureStore(dst,vec3i(i),vec4f(0));}`,'clear-pressure-source');
    }
    this.vort = this.texture(this.N);
    this.levels = [];
    for (let n = this.N; n >= 4; n /= 2)
      this.levels.push({
        n,
        p: [this.texture(n, 'r32float'), this.texture(n, 'r32float')],
        b: this.texture(n, 'r32float'),
        current: 0,
      });
    // Static approved fuel artwork, never temporal fire frames.
    const response = await fetch(new URL('../source/source-native.rgba8.bin', import.meta.url));
    if (!response.ok) throw Error('CYBR fuel artwork could not be loaded.');
    const sourceBytes = new Uint8Array(await response.arrayBuffer());
    if (sourceBytes.length !== 896 * 504 * 4) throw Error('CYBR fuel artwork has an invalid size.');
    const source = d.createTexture({
      size: [896, 504],
      format: 'rgba8unorm',
      usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST,
    });
    d.queue.writeTexture({ texture: source }, sourceBytes, { bytesPerRow: 896 * 4 }, [896, 504]);
    this.sigilSource = { view: source.createView() };
    this.resources.push(source);
    this.objectSettings = d.createBuffer({
      size: 48,
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    });
    this.objectModels = {};
    this.emptyWoodNodes=d.createBuffer({size:64,usage:GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_DST});
    this.emptyWoodPose=d.createBuffer({size:64,usage:GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_DST});
    this.emptyWoodMetadata=d.createBuffer({size:16,usage:GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_DST});
    this.emptyWoodOwners=d.createBuffer({size:64**3*4,usage:GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_DST});
    this.emptyWoodFlux=d.createBuffer({size:64,usage:GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_DST});
    this.resources.push(this.emptyWoodNodes,this.emptyWoodPose,this.emptyWoodMetadata,this.emptyWoodOwners,this.emptyWoodFlux);
    d.queue.writeBuffer(this.emptyWoodPose,0,new Float32Array([0,0,0,-1,0,0,0,1,0,0,0,0,0,0,0,0]));
    this.woodCollision=await new WoodCollision(this).init();
    this.emptyObject = this.texture(1);
    this.surface = [this.texture(64, 'rgba32float'), this.texture(64, 'rgba32float')];
    this.damage = [this.texture(64, 'rgba32float'), this.texture(64, 'rgba32float')];
    this.forestMesh = null;
    this.rendererFamilies = new Map();
    this.usingTree = false;
    this.surfacePipeline = await this.pipeline(this.chemistryCode(basicSurfaceWGSL,'gas'), 'surface-fuel');
    this.surfaceResetPipeline = await this.pipeline(basicSurfaceWGSL, 'surface-reset', 'reset');
    this.damageResetPipeline = await this.pipeline(damageResetWGSL, 'wood-damage-reset');
    this.treeSurfacePipeline = this.surfacePipeline;
    this.emberBuffer = d.createBuffer({
      size: 2048 * 32,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    });
    this.emberPipeline = await this.pipeline(this.chemistryCode(emberComputeWGSL,'gas'), 'embers');
    const emberModule = d.createShaderModule({ code: this.chemistryCode(emberRenderWGSL,'gas') });
    this.emberRender = await d.createRenderPipelineAsync({
      layout: 'auto',
      vertex: { module: emberModule, entryPoint: 'vertex' },
      fragment: {
        module: emberModule,
        entryPoint: 'fragment',
        targets: [
          {
            format: 'rgba8unorm',
            blend: {
              color: { srcFactor: 'src-alpha', dstFactor: 'one', operation: 'add' },
              alpha: { srcFactor: 'zero', dstFactor: 'one', operation: 'add' },
            },
          },
        ],
      },
    });
    await this.initFloorFuel();
    if(this.flowDetail){
      if(this.adaptive)throw Error('Advected flow detail needs the global flow path');
      this.materialIndex=0;
      this.materialFlow=Array.from({length:2},()=>{const t=d.createTexture({label:'advected-material-flow',size:[64,64,64],dimension:'3d',format:'rgba16float',usage:GPUTextureUsage.TEXTURE_BINDING|GPUTextureUsage.STORAGE_BINDING});this.resources.push(t);return {t,view:t.createView()};});
      this.materialPipeline=await this.pipeline(flowDetailShader(this.N),'advected-material-flow');
      this.materialClear=await this.pipeline('@group(0) @binding(0) var dst:texture_storage_3d<rgba16float,write>;@compute @workgroup_size(4,4,4) fn main(@builtin(global_invocation_id) i:vec3u){textureStore(dst,vec3i(i),vec4f(0));}','clear-material-flow');
    }
    const shaders=this.simulationShaderSet(this.powerKind,this.hasPowers);
    await Promise.all(Object.entries(shaders).map(async ([name,code])=>{
      this.pipelines[name]=await this.pipeline(code,name);
    }));
    this.measureProjection=await this.pipeline(projectionMeasureShader(this.N),'measure-final-velocity');
    this.sourcePipelineCache.set(this.powerKind,this.sourcePipelineFamily());
    if(this.hasPowers){this.powerContacts=new PowerContacts(this);await this.powerContacts.select(this.powerKind);}
    await Promise.all(this.levels.map(async level=>{
      level.kernels={};
      await Promise.all(Object.entries(pressureShaders(level.n)).map(async ([name,code])=>{
        level.kernels[name]=await this.pipeline(code,'pressure-'+name+'-'+level.n);
      }));
    }));
    await this.prepareRenderer(false);
    this.output = d.createTexture({
      size: [this.canvas.width, this.canvas.height],
      format: 'rgba8unorm',
      usage:
        GPUTextureUsage.RENDER_ATTACHMENT |
        GPUTextureUsage.TEXTURE_BINDING |
        GPUTextureUsage.COPY_SRC,
    });
    this.outputView = this.output.createView();
    this.resources.push(this.output);
    const present = d.createShaderModule({
      code: `@group(0) @binding(0) var image:texture_2d<f32>;@vertex fn vs(@builtin(vertex_index) i:u32)->@builtin(position) vec4f{let q=vec2f(f32((i<<1u)&2u),f32(i&2u));return vec4f(q*2.-1.,0,1);}@fragment fn fs(@builtin(position) p:vec4f)->@location(0) vec4f{return textureLoad(image,vec2i(p.xy),0);}`,
    });
    this.present = await d.createRenderPipelineAsync({
      layout: 'auto',
      vertex: { module: present, entryPoint: 'vs' },
      fragment: { module: present, entryPoint: 'fs', targets: [{ format: this.format }] },
    });
    if (d.features.has('timestamp-query')) {
      this.query = d.createQuerySet({ type: 'timestamp', count: 102 });
      this.queryResolve = d.createBuffer({
        // Twelve substeps have eight timestamps each. Whole-solve stamps
        // resolve at byte768; lighting/render resolve at byte1024.
        size: 1056,
        usage: GPUBufferUsage.QUERY_RESOLVE | GPUBufferUsage.COPY_SRC,
      });
      for (const slot of this.telemetrySlots)
        slot.query = d.createBuffer({
          size: 816,
          usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ,
        });
      // Existing isolated kernel probes use this buffer directly.
      this.queryRead = this.telemetrySlots[0].query;
    }
    this.visibleBricks = d.createBuffer({ size: 32 ** 3 * 4, usage: GPUBufferUsage.STORAGE });
    if (this.useLightReceivers) this.lightingReceivers=createLightingReceivers(d);
    this.dilatePipeline = await this.pipeline(this.useLightReceivers ? dilateReceiversWGSL : dilateWGSL, 'visible-bricks');
    this.light = this.texture(64);
    if(this.phaseLighting){const t=d.createTexture({label:'volume-light-phase-moments',size:[64,64,192],dimension:'3d',format:'rgba16float',usage:GPUTextureUsage.TEXTURE_BINDING|GPUTextureUsage.STORAGE_BINDING});this.resources.push(t);this.phaseLight={t,view:t.createView()};}
    this.fireLights = d.createBuffer({ size: 8 * 64, usage: GPUBufferUsage.STORAGE });
    this.lightSeeds = d.createBuffer({ size: 8 * 64, usage: GPUBufferUsage.STORAGE });
    this.roomTargets = [0, 1].map(() => {
      const t = d.createTexture({
        size: [ROOM_SIZE*5, ROOM_SIZE],
        format: 'rgba16float',
        usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.STORAGE_BINDING,
      });
      this.resources.push(t);
      return { t, view: t.createView() };
    });
    this.clearPipeline = await this.pipeline(
      `
@group(0) @binding(0) var a:texture_storage_3d<rgba16float,write>;
@group(0) @binding(1) var b:texture_storage_3d<rgba16float,write>;
@group(0) @binding(2) var c:texture_storage_3d<rgba16float,write>;
@compute @workgroup_size(4,4,4) fn main(@builtin(global_invocation_id) id:vec3u){
 if(any(id>=textureDimensions(a))){return;}textureStore(a,vec3i(id),vec4f(0));textureStore(b,vec3i(id),vec4f(0));textureStore(c,vec3i(id),vec4f(0));
}`,
      'clear-state',
    );
    this.vi = 0;
    this.ci = 0;
    if (this.adaptive) await this.initAdaptive();
    if (this.pressureWork) this.adaptivePressure = await AdaptivePressure.create(d,this.N);
    if (this.useLightWork) await this.initLightingWork();
    const setup = d.createCommandEncoder();
    this.chemistryPool?.encodeReset(setup);
    this.clearFloorFuel(setup);
    this.resetSurface(setup);
    d.queue.submit([setup.finish()]);
  }
  simulationShaderSet(powerKind,hasPowers=powerKind!==null){
    const shaders=simulationShaders(this.N,this.D,{flowSupport:this.adaptive,directVorticity:true,hasPowers,powerKind,pressureCache:this.usePressureCache,woodCadence:this.multirateWood,subgroups:this.device.features?.has?.('subgroups')??false,prune:false});
    if(this.flowDetail)shaders.correctVelocity=flowDetailVelocity(shaders.correctVelocity);
    if(this.transport==='flux'){
      const start=shaders.correctScalar.indexOf(' let forward=textureLoad(pred,vec3i(i),0);');
      const end=shaders.correctScalar.indexOf(' let goal=',start);
      if(start<0||end<0)throw Error('Chemical transport marker changed');
      shaders.correctScalar=shaders.correctScalar.slice(0,start)+' var c=max(textureLoad(old,vec3i(i),0),vec4f(0));\n'+shaders.correctScalar.slice(end);
      shaders.correctScalar=shaders.correctScalar.replace('@group(0) @binding(4) var pred:texture_3d<f32>;','');
      shaders.correctScalar=shaders.correctScalar.replace(';let back=trace(v,x,p.step.x);',';');
      shaders.advectScalar=conservativeFluxShader(this.N,this.D,this.fluxBlock);
    }
    if(this.reactionPrecision)shaders.correctScalar=reactionPrecisionShader(shaders.correctScalar);
    if(this.fuseFinalFlux)shaders.correctScalar=fusedFluxReactionShader(shaders.correctScalar,this.N,this.D);
    if (this.chemistryPool) Object.assign(shaders,
      brickPoolScalarShaders(this.chemistryPool.plan,{N:this.N,shaders}),
      {correctVelocity:brickPoolVelocityShader(this.chemistryPool.plan,{N:this.N,source:shaders.correctVelocity})});
    if(this.transport==='flux'){
      for(let axis=0;axis<3;axis++)shaders['advectScalar'+axis]=shaders.advectScalar.replaceAll('fluxStep.axis',axis+'u').replaceAll('fluxStep.seed',((axis*0x9e3779b9)>>>0)+'u');
      delete shaders.advectScalar;
    }
    for(const name of Object.keys(shaders))shaders[name]=pruneShaderFunctions(shaders[name]);
    return shaders;
  }
  sourcePipelineFamily(){
    const family=Object.fromEntries(['correctVelocity','correctScalar','buildBricks'].map(name=>[name,this.pipelines[name]]));
    if(this.adaptive&&this.flowPipelines)family.flowFamily=Object.fromEntries(['sourceWork','coarseCorrect','fineCorrect'].map(name=>[name,this.flowPipelines[name]]));
    return family;
  }
  async selectPowerKind(kind){
    if(this.powerKind===kind)return;
    let family=this.sourcePipelineCache.get(kind);
    if(!family){
      const shaders=this.simulationShaderSet(kind);
      const pending=(async()=>{
        const family=Object.fromEntries(await Promise.all(['correctVelocity','correctScalar','buildBricks'].map(async name=>[name,await this.pipeline(shaders[name],name)])));
        if(this.adaptive){
          const flow=adaptiveFlowShaders(this.N,this.D,8,{hasPowers:kind!==null,powerKind:kind,pressureCache:this.usePressureCache});
          family.flowFamily=Object.fromEntries(await Promise.all(['sourceWork','coarseCorrect','fineCorrect'].map(async name=>[name,await this.pipeline(name==='sourceWork'?flow[name]:this.chemistryCode(flow[name],'chem'),'adaptive-flow-'+name)])));
        }
        return family;
      })();
      this.sourcePipelineCache.set(kind,pending);
      try{family=await pending;}catch(error){this.sourcePipelineCache.delete(kind);throw error;}
      this.sourcePipelineCache.set(kind,family);
    }else family=await family;
    if(this.destroyed)throw Error('The solver closed during source compilation');
    const {flowFamily,...simulationFamily}=family;
    Object.assign(this.pipelines,simulationFamily);
    if(flowFamily)Object.assign(this.flowPipelines,flowFamily);
    this.powerKind=kind;this.hasPowers=kind!==null;
    if(this.hasPowers){if(!this.powerContacts)this.powerContacts=new PowerContacts(this);await this.powerContacts.select(kind);}
  }
  async initFloorFuel() {
    const d=this.device, n=FLOOR_FUEL_SIZE;
    const make=format=>{
      const t=d.createTexture({size:[n,n],format,usage:GPUTextureUsage.TEXTURE_BINDING|GPUTextureUsage.STORAGE_BINDING|GPUTextureUsage.COPY_DST});
      this.resources.push(t);return {t,view:t.createView()};
    };
    this.floorFuel=[make('rgba32float'),make('rgba32float')];
    this.floorWear=[make('rgba32float'),make('rgba32float')];
    this.floorDeposits=make('r32float');
    this.floorUpload=new Float32Array(n*n);
    this.floorUpdate=await this.pipeline(this.chemistryCode(floorFuelUpdateWGSL),'floor-fuel');
    this.floorClear=await this.pipeline(floorFuelClearWGSL,'floor-fuel-clear');
    this.floorWearClear=await this.pipeline(floorWoodWearClearWGSL,'floor-wood-wear-clear');
    this.floorDepositClear=await this.pipeline(floorDepositsClearWGSL,'floor-deposits-clear');
  }
  floorPass(encoder,pipeline,items) {
    const pass=encoder.beginComputePass();pass.setPipeline(pipeline);
    pass.setBindGroup(0,this.group(pipeline,items));
    pass.dispatchWorkgroups(FLOOR_FUEL_SIZE/8,FLOOR_FUEL_SIZE/8);pass.end();
  }
  clearFloorFuel(encoder) {
    this.floorPass(encoder,this.floorClear,[[0,this.floorFuel[0]],[1,this.floorFuel[1]],[2,this.floorDeposits]]);
    this.floorPass(encoder,this.floorWearClear,[[0,this.floorWear[0]],[1,this.floorWear[1]]]);
    this.floorIndex=0;this.hasFloorFuel=false;this.floorIgnition=false;this.fuelBrush.clear();
    this.floorFuelKind=null;
  }
  clearFuel() {
    const encoder=this.device.createCommandEncoder();this.clearFloorFuel(encoder);
    this.device.queue.submit([encoder.finish()]);this.lightReady=false;
  }
  dropFuel(at,previous=null) {
    if(this.hasFloorFuel&&this.floorFuelKind!==this.fuel)this.clearFuel();
    this.floorFuelKind=this.fuel;
    const changed=previous?this.fuelBrush.stroke(previous,at):this.fuelBrush.stamp(...at);
    if(changed){this.hasFloorFuel=true;this.previousDt=0;this.lightReady=false;}
    return changed;
  }
  igniteFuel(){
    if(!this.hasFloorFuel||this.smoke)return false;
    this.floorIgnition=true;this.previousDt=0;this.lightReady=false;return true;
  }
  updateFloorFuel(encoder,p,ci) {
    if(!this.hasFloorFuel)return;
    const packet=this.fuelBrush.consume();
    if(packet)this.device.queue.writeTexture({texture:this.floorDeposits.t},expandFuelDeposits(packet.data,this.floorUpload),{bytesPerRow:FLOOR_FUEL_SIZE*4},[FLOOR_FUEL_SIZE,FLOOR_FUEL_SIZE]);
    this.floorPass(encoder,this.floorUpdate,[[0,{buffer:p}],[1,this.sampler],[2,this.c[ci]],
      [3,this.floorFuel[this.floorIndex]],[4,this.floorDeposits],[5,this.floorFuel[1-this.floorIndex]],
      [6,this.floorWear[this.floorIndex]],[7,this.floorWear[1-this.floorIndex]],...this.chemistryBindings(ci)]);
    this.floorIndex=1-this.floorIndex;
    this.floorIgnition=false;
    if(packet)this.floorPass(encoder,this.floorDepositClear,[[0,this.floorDeposits]]);
  }
  floorBindings(render=false){return [[32,this.floorFuel[this.floorIndex]],...(render&&this.floorWear?[[45,this.floorWear[this.floorIndex]]]:[])];}
  async initAdaptive() {
    const d = this.device, C = this.N / 2, T = (this.N / 8) ** 3;
    const storage = GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST;
    this.flowMask = d.createBuffer({ size:T*4, usage:storage });
    this.flowTiles = d.createBuffer({ size:T*16, usage:storage });
    this.flowCount = d.createBuffer({ size:4, usage:storage });
    this.flowCommands = d.createBuffer({ size:ADAPTIVE_FLOW_COMMAND_BYTES, usage:storage | GPUBufferUsage.INDIRECT | GPUBufferUsage.COPY_SRC });
    d.queue.writeBuffer(this.flowCommands,0,initialAdaptiveFlowCommands(this.N,this.D));
    this.flowChemBricks = d.createBuffer({ size:(this.D/8)**3*16, usage:storage });
    this.flowChemArgs = d.createBuffer({ size:12, usage:storage | GPUBufferUsage.INDIRECT });
    d.queue.writeBuffer(this.flowChemArgs,0,new Uint32Array([0,2,4]));
    this.coarseV = Array.from({length:3},()=>this.texture(C+1));
    this.coarseCurl = this.texture(C);
    this.flowPipelines = {};
    const shaders=adaptiveFlowShaders(this.N,this.D,8,{hasPowers:this.hasPowers,powerKind:this.powerKind,pressureCache:this.usePressureCache});
    for (const [name, code] of Object.entries(shaders)) {
      this.flowPipelines[name] = await this.pipeline(
        name === 'coarseCorrect' || name === 'fineCorrect' ? this.chemistryCode(code,'chem') : code,
        'adaptive-flow-'+name);
    }
    this.flowChemistryPipeline = await this.pipeline(shaders.mark,'adaptive-flow-chemistry','chemistry');
    this.flowFinishPipeline = await this.pipeline(shaders.build,'adaptive-flow-finish','finish');
    this.sourcePipelineCache.set(this.powerKind,this.sourcePipelineFamily());
  }
  async initLightingWork() {
    const d=this.device;
    this.lightingWork = createLightingWork(d);
    this.lightingPipelines = {};
    for (const [name,code] of Object.entries(lightingWorkShaders))
      this.lightingPipelines[name] = await this.pipeline(this.phaseLighting&&name==='scatter'?code.replace('@group(0) @binding(3) var lightOut:', '@group(0) @binding(4) var phaseOut:texture_storage_3d<rgba16float,write>;\n@group(0) @binding(3) var lightOut:').replace('textureStore(lightOut,vec3i(at),vec4f(0,0,0,1));','textureStore(lightOut,vec3i(at),vec4f(0,0,0,1));textureStore(phaseOut,vec3i(at),vec4f(0));textureStore(phaseOut,vec3i(at)+vec3i(0,0,64),vec4f(0));textureStore(phaseOut,vec3i(at)+vec3i(0,0,128),vec4f(0));'):code,'lighting-work-'+name);
    this.lightingGroups = {
      build:this.group(this.lightingPipelines.build,[[0,{buffer:this.visibleBricks}],[1,{buffer:this.lightingWork.counts}]]),
      prefix:this.group(this.lightingPipelines.prefix,[[0,{buffer:this.lightingWork.counts}],[1,{buffer:this.lightingWork.offsets}],[2,{buffer:this.lightingWork.dispatch}]]),
      scatter:this.group(this.lightingPipelines.scatter,[[0,{buffer:this.visibleBricks}],[1,{buffer:this.lightingWork.offsets}],[2,{buffer:this.lightingWork.indices}],[3,this.light],...(this.phaseLighting?[[4,this.phaseLight]]:[])]),
    };
  }
  indirectRun(encoder,pipeline,items,commands,offset=0,work=null) {
    const pass=encoder.beginComputePass();pass.setPipeline(pipeline);
    pass.setBindGroup(0,this.group(pipeline,items));
    if(work)pass.dispatchWorkgroups(...work);else pass.dispatchWorkgroupsIndirect(commands,offset);
    pass.end();
  }
  chemistryCode(code,texture='chem',render=false) {
    return this.chemistryPool ? pooledChemistryConsumer(code,this.chemistryPool.plan,{
      texture, ...(render ? {atlasBinding:25,pagesBinding:28,metadataBinding:29} : {}),
    }) : code;
  }
  chemistryBindings(index,render=false) {
    const pool=this.chemistryPool;
    return pool ? [...(pool.plan.sharedStorage?[]:[[render?25:20,pool.fields[index]]]),
      [render?28:23,{buffer:pool.pageTable}],[render?29:24,{buffer:pool.metadata}]] : [];
  }
  scalarBindings(ci,correct=false,predictor=2,destination=1-ci) {
    const pool=this.chemistryPool;
    if(pool?.plan.sharedStorage)return [[23,{buffer:pool.pageTable}],[24,{buffer:pool.metadata}]];
    return pool ? [[20,pool.fields[ci]],
      ...(!correct||this.transport!=='flux'?[[21,pool.fields[predictor]]]:[]),
      ...(correct&&!pool.plan.sharedStorage?[[22,pool.fields[destination]]]:[]),
      [23,{buffer:pool.pageTable}],[24,{buffer:pool.metadata}]] : [];
  }
  buildScalarWork(encoder,p,ci) {
    encoder.clearBuffer(this.indirect,0,4);
    this.dispatch(encoder,this.pipelines.buildBricks,[[0,{buffer:p}],[2,{buffer:this.masks[ci]}],
      [3,{buffer:this.masks[1-ci]}],[4,{buffer:this.bricks}],[5,{buffer:this.indirect}],[1,this.sampler],...this.objectBindings(),...this.floorBindings(),...this.woodFluxBindings()],this.D/8);
  }
  adaptiveVelocity(encoder,base,vi,ci) {
    const a=this.flowPipelines,k=this.pipelines;
    encoder.clearBuffer(this.flowChemArgs,0,4);
    const classify=(pipeline,items,name)=>this.indirectRun(encoder,pipeline,items,this.flowCommands,ADAPTIVE_FLOW_OFFSETS[name]);
    classify(a.sourceWork,[...base,[2,{buffer:this.opticalMasks[ci]}],[3,{buffer:this.opticalMasks[1-ci]}],
      [4,{buffer:this.flowChemBricks}],[5,{buffer:this.flowChemArgs}],...this.objectBindings(),...this.floorBindings(),...this.woodFluxBindings()],'sourceWork');
    classify(a.restrict,[[0,this.v[vi]],[1,this.coarseV[0]]],'restrict');
    encoder.clearBuffer(this.flowMask);
    classify(this.flowChemistryPipeline,[[2,{buffer:this.flowChemBricks}],[3,{buffer:this.flowChemArgs}],[4,{buffer:this.flowMask}]],'chemistry');
    classify(a.mark,[[0,this.v[vi]],[1,this.coarseV[0]],[4,{buffer:this.flowMask}]],'mark');
    encoder.clearBuffer(this.flowCount);
    classify(a.build,[[0,{buffer:this.flowMask}],[1,{buffer:this.flowTiles}],[2,{buffer:this.flowCount}]],'build');
    // finish writes flowCommands, so it cannot use that same buffer as its
    // indirect source within this dispatch. One fixed workgroup handles preflight.
    this.indirectRun(encoder,this.flowFinishPipeline,[[1,{buffer:this.flowTiles}],[2,{buffer:this.flowCount}],[3,{buffer:this.flowCommands}]],null,0,[1]);
    const run=(pipeline,items,offset)=>this.indirectRun(encoder,pipeline,items,this.flowCommands,offset);
    run(a.coarseAdvect,[...base,[2,this.coarseV[0]],[3,this.coarseV[2]]],0);
    run(a.coarseCurl,[[1,this.sampler],[2,this.coarseV[0]],[3,this.coarseCurl]],0);
    run(a.coarseCorrect,[...base,[2,this.coarseV[0]],[3,this.coarseV[2]],[4,this.c[ci]],
      [5,this.coarseCurl],[6,this.coarseV[1]],[8,this.sigilSource],...this.objectBindings(true),...this.chemistryBindings(ci),[60,{buffer:this.shockStage?.bindings()||this.emptyShockRM}],...this.velocitySourceBindings()],0);
    run(a.fill,[[0,this.coarseV[2]],[1,this.v[2]]],12);
    run(a.fillCell,[[0,this.coarseCurl],[1,this.vort],[2,this.sampler]],12);
    run(a.fill,[[0,this.coarseV[1]],[1,this.v[1-vi]]],12);
    const tiles=[14,{buffer:this.flowTiles}];
    run(a.fineAdvect,[...base,[2,this.v[vi]],[3,this.v[2]],tiles],24);
    run(a.fineCurl,[[1,this.sampler],[2,this.v[vi]],[3,this.vort],tiles],36);
    run(a.fineCorrect,[...base,[2,this.v[vi]],[3,this.v[2]],[4,this.c[ci]],
      [5,this.vort],[6,this.v[1-vi]],[8,this.sigilSource],...this.objectBindings(true),tiles,...this.chemistryBindings(ci),[60,{buffer:this.shockStage?.bindings()||this.emptyShockRM}],...this.velocitySourceBindings()],36);
    run(k.advectVelocity,[...base,[2,this.v[vi]],[3,this.v[2]]],48);
    run(k.curl,[[1,this.sampler],[2,this.v[vi]],[3,this.vort]],60);
    run(k.correctVelocity,[...base,[2,this.v[vi]],[3,this.v[2]],[4,this.c[ci]],
      [5,this.vort],[6,this.v[1-vi]],[8,this.sigilSource],...this.objectBindings(true),...this.chemistryBindings(ci),[60,{buffer:this.shockStage?.bindings()||this.emptyShockRM}],...this.velocitySourceBindings()],72);
  }
  async prepareRenderer(tree) {
    if (!this.rendererFamilies.has(tree)) {
      const code = Object.fromEntries(Object.entries(rendererShaders(tree,false,false,this.phaseLighting,this.D)).map(([key,value])=>
        [key,this.chemistryCode(value,'chem',true)])),
        module = this.device.createShaderModule({ code: code.render });
      const info = await module.getCompilationInfo();
      if (info.messages.some((m) => m.type === 'error'))
        throw Error(info.messages.map((m) => m.message).join('\n'));
      const renderPipeline = await this.device.createRenderPipelineAsync({
        layout: 'auto',
        vertex: { module, entryPoint: 'vertex' },
        fragment: { module, entryPoint: 'fragment', targets: [{ format: 'rgba8unorm' }] },
        primitive: { topology: 'triangle-list' },
      });
      const family = { renderPipeline };
      for (const [key, shader, entry] of [
        ['lightPipeline', 'light', 'main'],
        ...(this.useLightReceivers ? [['lightReceiverPipeline','lightReceivers','main']] : []),
        ...(this.useLightWork ? [['lightWorkPipeline','lightWork','main']] : []),
        ['roomPipeline', 'room', 'main'],
        ['bouncePipeline', 'room', 'bounce'],
        ['gatherPipeline', 'gather', 'main'],
        ['gatherAdaptivePipeline', 'gatherAdaptive', 'main'],
      ])
        family[key] = await this.pipeline(code[shader], (tree ? 'tree-' : '') + key, entry);
      this.rendererFamilies.set(tree, family);
    }
    Object.assign(this, this.rendererFamilies.get(tree));
  }
  async prepareSource() {
    const requested = this.objectId,
      tree = ['cybr-tree','logs','house','wood-sigil'].includes(requested);
    if (requested && !this.objectModels[requested]) {
      const response = await fetch(
        new URL('./objects/' + (requested==='cybr-tree'?'forest-tree/wood-solid.rgba16.bin':['logs','house','wood-sigil'].includes(requested)?requested+'/solid.rgba16.bin':requested+'.rgba16.bin'), import.meta.url),
      );
      if (!response.ok) throw Error('Object geometry unavailable: ' + requested);
      const bytes = new Uint8Array(await response.arrayBuffer());
      if (bytes.length !== 64 ** 3 * 8) throw Error('Invalid object geometry');
      const model = this.texture(64);
      this.device.queue.writeTexture(
        { texture: model.t },
        bytes,
        { bytesPerRow: 64 * 8, rowsPerImage: 64 },
        [64, 64, 64],
      );
      this.objectModels[requested] = model;
    }
    if (requested !== this.objectId) return this.prepareSource();
    if(this.woodStructureId!==requested){
      if(this.woodOwners&&this.woodOwners!==this.emptyWoodOwners){this.woodOwners.destroy();this.resources=this.resources.filter(r=>r!==this.woodOwners);}
      this.woodStructure?.dispose();this.woodStructure=null;this.woodOwners=this.emptyWoodOwners;this.woodStructureId=undefined;
      this.woodFlux?.destroy();this.woodFlux=null;this.woodFluxMetadata=null;
      try{if(['cybr-tree','logs','house','wood-sigil'].includes(requested)){
        const directory=requested==='cybr-tree'?'forest-tree/structure':requested;
        const base=new URL('./objects/'+directory+'/',import.meta.url);
        this.woodStructure=await new WoodStructure(this.device).init(base);
        const bytes=await(await fetch(new URL('voxel-owners.bin',base))).arrayBuffer();
        if(bytes.byteLength!==64**3*4)throw Error('Invalid wood ownership map');
        this.woodOwners=this.device.createBuffer({label:'wood voxel owners',size:bytes.byteLength,usage:GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_DST});
        this.device.queue.writeBuffer(this.woodOwners,0,bytes);this.resources.push(this.woodOwners);
        this.woodFlux=await new WoodFlux(this.device,{group:(pipeline,entries)=>this.group(pipeline,entries)}).init();
        this.woodFluxMetadata=await this.woodFlux.loadMetadata(new URL(requested==='cybr-tree'?'../flux-metadata.rgba32.bin':'flux-metadata.rgba32.bin',base));
      }this.woodStructureId=requested;}catch(error){
        this.woodStructure?.dispose();this.woodStructure=null;this.woodFlux?.destroy();this.woodFlux=null;this.woodFluxMetadata=null;
        if(this.woodOwners!==this.emptyWoodOwners){this.woodOwners.destroy();this.resources=this.resources.filter(r=>r!==this.woodOwners);}this.woodOwners=this.emptyWoodOwners;
        this.cache.clear();throw error;
      }
      this.cache.clear();
    }
    if(this.forestMesh&&this.meshObjectId!==requested){this.forestMesh.destroy();this.forestMesh=null;this.cache.clear();}
    if (tree && !this.forestMesh) {
      this.updateObject();
      const init = this.device.createCommandEncoder();
      for (const damage of this.damage)
        this.dispatch(
          init,
          this.damageResetPipeline,
          [
            [13, { buffer: this.objectSettings }],
            [16, damage],
          ],
          64,
        );
      this.device.queue.submit([init.finish()]);
      this.forestMesh = new ForestMesh(this);
      this.meshObjectId=requested;
    }
    if (tree) await this.forestMesh.load();
    if (!tree && this.forestMesh) {
      this.forestMesh.destroy();
      this.forestMesh = null;
      this.cache.clear();
    }
    if (tree !== this.usingTree) {
      await this.prepareRenderer(tree);
      this.usingTree = tree;
      this.lightReady = false;
    }
    if (requested !== this.objectId) return this.prepareSource();
    if(requested&&!this.geometryPressure)this.geometryPressure=await GeometryPressure.create(this);
    if(!requested&&this.geometryPressure){this.geometryPressure.destroy();this.geometryPressure=null;this.cache.clear();}
    if(this.geometryPressure)this.geometryPressure.enabled=true;
  }
  makeGeometryMeasure(){return this.pipeline(projectionMeasureShader(this.N,{weighted:true}),'measure-geometry-velocity');}
  meshBindings() {
    return this.usingTree ? this.forestMesh.bindings() : [];
  }
  meshShadowBindings() {
    return this.usingTree ? this.forestMesh.shadowBindings() : [];
  }
  group(pipeline, items) {
    // Entries are explicit because dead-code elimination removes unused slots.
    const id = (o) => {
      if (!this.ids.has(o)) this.ids.set(o, ++this.nextId);
      return this.ids.get(o);
    };
    const key =
      id(pipeline) + ':' + items.map(([b, r]) => b + '-' + id(r.view || r.buffer || r)).join(',');
    if (!this.cache.has(key))
      this.cache.set(
        key,
        this.device.createBindGroup({
          layout: pipeline.getBindGroupLayout(0),
          entries: items.map(([binding, resource]) => ({
            binding,
            resource: resource.view || resource,
          })),
        }),
      );
    return this.cache.get(key);
  }
  dispatch(encoder, pipeline, items, n) {
    const pass = this.pressurePass || encoder.beginComputePass();
    pass.setPipeline(pipeline);
    pass.setBindGroup(0, this.group(pipeline, items));
    const xy = pipeline.label.startsWith('pressure-') ? 8 : 4;
    const x = pipeline.label === 'advectVelocity' ? 8 : xy;
    pass.dispatchWorkgroups(Math.ceil(n / x), Math.ceil(n / xy), Math.ceil(n / 4));
    if (!this.pressurePass) pass.end();
  }
  sparse(encoder, pipeline, items, indirect=null) {
    const pass = encoder.beginComputePass();
    pass.setPipeline(pipeline);
    pass.setBindGroup(0, this.group(pipeline, items));
    pass.dispatchWorkgroupsIndirect(indirect || this.chemistryPool?.commands || this.indirect,
      !indirect&&this.chemistryPool ? POOL_INDIRECT.scalar : 0);
    pass.end();
  }
  vcycle(encoder, l = 0) {
    const level = this.levels[l];
    const geometry=this.geometryPressure?.enabled?this.geometryPressure:null;
    const kernels=geometry?geometry.kernels[l]:level.kernels;
    const weights=name=>geometry&&name!=='prolong'?[[4,geometry.weights[l]]]:[];
    const smooth = (count) => {
      if (l === 0 && !geometry && this.adaptivePressure && count === this.adaptivePressure.sweeps) {
        level.current = this.adaptivePressure.encodeSegment(encoder,level.p,level.b,level.current,this.pressurePass);
        return;
      }
      for (let i = 0; i < count; i++) {
        this.dispatch(
          encoder,
          kernels.smooth,
          [
            [0, level.p[level.current]],
            [1, level.b],
            [2, level.p[1 - level.current]],...weights("smooth"),
          ],
          level.n,
        );
        level.current = 1 - level.current;
      }
    };
    if (l === this.levels.length - 1) {
      if (kernels.coarse) {
        this.dispatch(encoder, kernels.coarse, [
          [0, level.p[level.current]],
          [1, level.b],
          [2, level.p[1 - level.current]],...weights("coarse"),
        ], level.n);
        level.current = 1 - level.current;
      } else smooth(24);
      return;
    }
    smooth(3);
    const coarse = this.levels[l + 1];
    coarse.current = 0;
    this.dispatch(
      encoder,
      kernels.restrict,
      [
        [0, level.p[level.current]],
        [1, level.b],
        [2, coarse.b],
        [3, coarse.p[0]],...weights("restrict"),
      ],
      coarse.n,
    );
    this.vcycle(encoder, l + 1);
    this.dispatch(
      encoder,
      kernels.prolong,
      [
        [0, level.p[level.current]],
        [1, coarse.p[coarse.current]],
        [2, level.p[1 - level.current]],
      ],
      level.n,
    );
    level.current = 1 - level.current;
    smooth(3);
  }
  stamp(encoder, index) {
    if (this.query) {
      const pass = encoder.beginComputePass({
        timestampWrites: { querySet: this.query, beginningOfPassWriteIndex: index },
      });
      pass.end();
    }
  }
  step(encoder, dt, index, frameDt=dt) {
    this.stamp(encoder, index * 8);
    this.powerCasts?.updateContinuous({direction:this.powerDirection,strength:this.powerStrength,scale:this.effect[1]});
    // Reuse pressure only for a settled continuous source. A new burst or
    // source movement keeps the original two cycles and zero initial guess.
    const stationary =
      this.lastPressureSource &&
      this.source.every((v, i) => Math.abs(v - this.lastPressureSource[i]) < (0.25 * 6) / this.N);
    const warmPressure =
      this.effect[3] > 0.5 && this.burstAge > 0.12 && this.previousDt && stationary &&
      !this.powerCasts?.crossesImpulse(dt);
    const p = this.params[index];
    if(this.kindlingEnabled&&this.active&&this.burstAge>=0&&this.burstAge<WOOD_GAS_PILOT.durationS&&this.hasFloorFuel)this.floorIgnition=true;
    let shockTrigger=false;
    for(const cast of this.powerCasts?.slots||[]){if(!cast.active||!cast.definition?.blastWindows?.length)continue;for(const window of cast.definition.blastWindows)if(cast.age<=window.from&&cast.age+dt>window.from){shockTrigger=true;break;}if(shockTrigger)break;}
    const contactLive=(this.powerCasts?.slots||[]).some(c=>c.active&&c.definition?.blastWindows?.length&&c.age>=c.definition.windup&&c.age<=c.definition.duration);
    const shockTimeBeforeStep=this.shockRemaining;
    const shockReset=(shockTrigger||contactLive)&&shockTimeBeforeStep<=0;
    this.shockRemaining=(shockTrigger||contactLive)?.42:Math.max(0,this.shockRemaining-dt);
    const smokeDecay=advanceSmokeDecay(this.smokeDecayRemainder||0,dt);
    this.smokeDecayRemainder=smokeDecay.remainder;
    const data=this.simulationParams||(this.simulationParams=new Float32Array(96));
    data.set([
        dt,
        this.time,
        this.burstAge,
        this.smoke ? 1 : 0,
        ...this.source,
        this.active ? 1 : 0,
        this.seed,
        this.hasFloorFuel ? (this.floorIgnition ? 3 : 1) : 0,
        this.fuel,
        warmPressure ? dt / this.previousDt : 0,
        ...this.effect,
        ...this.dynamics,
        ...this.chemistry,
        smokeDecay.decayDt,this.floorFuelKind===.35?1:0,this.woodTimeScale||12,shockFlowTransferWeight(frameDt,shockReset?.42:shockTimeBeforeStep,index),
        ...this.powerUniform(),
      ]);
    data.fill(0,32);
    this.powerCasts?.write(data,32);
    this.device.queue.writeBuffer(p,0,data);
    if(this.hasPowers)this.powerContacts?.encode(encoder,p);
    if(this.shockRemaining>0&&this.shockStage)this.shockStage.encode(encoder,p,dt,index,this.frameNumber%3,shockReset);
    this.previousDt = dt;
    this.lastPressureSource = [...this.source];
    const base = [
        [0, { buffer: p }],
        [1, this.sampler],
      ],
      k = this.pipelines;
    const vi = this.vi,
      ci = this.ci;
    this.updateFloorFuel(encoder,p,ci);
    if (this.objectId && (!this.multirateWood || index===0)) {
      let woodParams=p,woodDt=dt;
      if(this.multirateWood){
        woodDt=frameDt;const woodData=new Float32Array(data);woodData[0]=frameDt;
        this.device.queue.writeBuffer(this.woodParams,0,woodData);
        this.device.queue.writeBuffer(this.woodPacket,0,new Float32Array([woodPacketFraction(dt,frameDt),frameDt,0,0]));
        woodParams=this.woodParams;
      }
      this.dispatch(
        encoder,
        this.usingTree ? this.treeSurfacePipeline : this.surfacePipeline,
        [
          [0,{buffer:woodParams}],[1,this.sampler],
          [2, this.c[ci]],
          ...this.chemistryBindings(ci),
          ...this.objectBindings(true),
          [14, this.surface[1 - this.si]],
          [15, this.damage[this.si]],
          [16, this.damage[1 - this.si]],
          ...this.woodPoseBindings(),
          [41,{buffer:this.woodOwners||this.emptyWoodOwners}],
        ],
        64,
      );
      this.si = 1 - this.si;
      this.woodStructure?.encode(encoder,{dt:woodDt,skin:this.surface[this.si].view,wear:this.damage[this.si].view,
        owners:this.woodOwners,metadata:this.woodFluxMetadata.view,origin:this.source,scale:this.effect[1]});
      this.woodFlux?.encode(encoder,{params:woodParams,settings:this.objectSettings,skin:this.surface[this.si],metadata:this.woodFluxMetadata,
        owners:this.woodOwners,nodes:this.woodStructure.staticBuffer,poses:this.woodStructure.state,
        normalizationBindings:[[1,this.sampler],...this.objectBindings()]});
    }
    if (this.chemistryPool) {
      this.buildScalarWork(encoder,p,ci);
      this.chemistryPool.encodeRequestsFromFineBricks(encoder,{bricks:this.bricks,indirect:this.indirect});
      this.chemistryPool.encodeTopology(encoder);
      this.chemistryPool.encodeMigrationToDense(encoder,ci,this.c[ci].view);
    }
    this.stamp(encoder,index*8+1);
    this.stamp(encoder,index*8+2);
    if (this.adaptive) {
      if (!this.chemistryPool) this.buildScalarWork(encoder,p,ci);
      this.adaptiveVelocity(encoder,base,vi,ci);
    } else {
    this.dispatch(
      encoder,
      k.advectVelocity,
      [...base, [2, this.v[vi]], [3, this.v[2]]],
      this.N + 1,
    );
    this.dispatch(
      encoder,
      k.curl,
      [
        [1, this.sampler],
        [2, this.v[vi]],
        [3, this.vort],
      ],
      this.N,
    );
    if(this.materialPipeline&&this.flowDetail){
      this.dispatch(encoder,this.materialPipeline,[[0,{buffer:p}],[1,this.sampler],[2,this.v[vi]],
        [3,this.materialFlow[this.materialIndex]],[4,this.materialFlow[1-this.materialIndex]],[5,this.vort]],64);
      this.materialIndex=1-this.materialIndex;
    }
    this.dispatch(
      encoder,
      k.correctVelocity,
      [
        ...base,
        [2, this.v[vi]],
        [3, this.v[2]],
        [4, this.c[ci]],
        [5, this.vort],
        [6, this.v[1 - vi]],
        [8, this.sigilSource],
        ...this.objectBindings(true),
        ...this.chemistryBindings(ci),
        ...(this.flowDetail?[[50,this.materialFlow[this.materialIndex]]]:[]),
        [60,{buffer:this.shockStage?.bindings()||this.emptyShockRM}],
        ...this.velocitySourceBindings(),
      ],
      this.N + 1,
    );
    }
    this.stamp(encoder, index * 8 + 3);
    this.stamp(encoder, index * 8 + 4);
    const geometry=this.geometryPressure?.enabled?this.geometryPressure:null;
    if(geometry){this.woodCollision?.encode(encoder);geometry.encode(encoder);}
    const geometryBindings=geometry?[[62,geometry.weights[0]]]:[];
    const fine = this.levels[0];
    const previous = fine.p[fine.current];
    fine.current = 1 - fine.current;
    this.dispatch(
      encoder,
      geometry?geometry.rhs:k.rhs,
      [
        [0, { buffer: p }],
        [2, this.v[1 - vi]],
        [3, fine.b],
        [4, fine.p[fine.current]],
        [5, previous],...geometryBindings,
      ],
      this.N,
    );
    this.pressurePass = encoder.beginComputePass();
    this.vcycle(encoder);
    if (!warmPressure) this.vcycle(encoder);
    this.pressurePass.end();
    this.pressurePass = null;
    this.dispatch(
      encoder,
      geometry?geometry.project:k.project,
      [
        [2, this.v[1 - vi]],
        [3, fine.p[fine.current]],
        [4, fine.b],
        [5, this.v[vi]],
        [6, { buffer: this.groupStats }],...geometryBindings,
      ],
      this.N + 1,
    );
    if(index===Math.round(frameDt/dt)-1)this.dispatch(encoder,geometry?geometry.measure:this.measureProjection,
      [[2,this.v[vi]],[4,fine.b],[6,{buffer:this.groupStats}],...geometryBindings],this.N+1);
    const reduce = encoder.beginComputePass();
    reduce.setPipeline(k.reduceStats);
    reduce.setBindGroup(
      0,
      this.group(k.reduceStats, [
        [0, { buffer: this.groupStats }],
        [1, { buffer: this.stats }],
      ]),
    );
    reduce.dispatchWorkgroups(1);
    reduce.end();
    this.stamp(encoder, index * 8 + 5);
    this.stamp(encoder, index * 8 + 6);
    if (!this.adaptive || this.chemistryPool) {
    encoder.clearBuffer(this.indirect, 0, 4);
    this.dispatch(
      encoder,
      k.buildBricks,
      [
        [0, { buffer: p }],
        [2, { buffer: this.masks[ci] }],
        [3, { buffer: this.masks[1 - ci] }],
        [4, { buffer: this.bricks }],
        [5, { buffer: this.indirect }],
        [1, this.sampler],
        ...this.objectBindings(),
        ...this.floorBindings(),
        ...this.woodFluxBindings(),
      ],
      this.D / 8,
    );
    }
    this.chemistryPool?.encodeRouteScalarDispatch(encoder,this.indirect);
    encoder.clearBuffer(this.masks[1 - ci]);
    encoder.clearBuffer(this.opticalMasks[1 - ci]);
    this.sparse(encoder,k.diffuseScalar,[[0,{buffer:p}],[3,this.c[ci]],[5,this.c[1-ci]],
      [6,{buffer:this.bricks}],...this.scalarBindings(ci,true,2,1-ci).filter(([slot])=>slot!==21)]);
    [this.c[ci],this.c[1-ci]]=[this.c[1-ci],this.c[ci]];
    if(this.chemistryPool){const fields=this.chemistryPool.fields;[fields[ci],fields[1-ci]]=[fields[1-ci],fields[ci]];}
    if(this.transport==='flux'){
      encoder.copyBufferToBuffer(this.indirect,0,this.fluxIndirect,0,4);
      const uniform=this.fluxParams[index];
      this.fluxUploadFloats[1]=dt;this.fluxUploadFloats[2]=this.time;
      this.device.queue.writeBuffer(uniform,0,this.fluxUpload);
      let current=ci;
      for(let axis=0;axis<(this.fuseFinalFlux?2:3);axis++){
        const destination=this.fuseFinalFlux?(axis===0?1-ci:2):(current+1)%3;
        this.sparse(encoder,k['advectScalar'+axis],[[1,this.sampler],[2,this.v[vi]],[3,this.c[current]],
          [4,this.c[destination]],[6,{buffer:this.bricks}],[46,{buffer:uniform}],[47,{buffer:this.fluxDiagnostics}],...this.scalarBindings(current,false,destination)],this.fluxIndirect);
        current=destination;
      }
      if(!this.fuseFinalFlux&&current!==ci){
        [this.c[ci],this.c[current]]=[this.c[current],this.c[ci]];
        if(this.chemistryPool){const fields=this.chemistryPool.fields;[fields[ci],fields[current]]=[fields[current],fields[ci]];}
      }
    }else this.sparse(encoder, k.advectScalar, [
      ...base,
      [2, this.v[vi]],
      [3, this.c[ci]],
      [4, this.c[2]],
      [6, { buffer: this.bricks }],
      ...this.scalarBindings(ci),
    ]);
    this.sparse(encoder, k.correctScalar, [
      ...base,
      ...(this.transport==='flux'&&!this.fuseFinalFlux?[]:[[2, this.v[vi]]]),
      [3, this.c[this.fuseFinalFlux?2:ci]],
      ...(this.transport==='flux'?[]:[[4, this.c[2]]]),
      [5, this.c[1 - ci]],
      [6, { buffer: this.bricks }],
      [7, { buffer: this.masks[1 - ci] }],
      [10, { buffer: this.opticalMasks[1 - ci] }],
      [8, this.sigilSource],
      ...this.objectBindings(true),
      ...this.scalarBindings(this.fuseFinalFlux?2:ci,true,2,1-ci),
      ...(this.fuseFinalFlux?[[46,{buffer:this.fluxParams[index]}],[47,{buffer:this.fluxDiagnostics}]]:[]),
      ...this.floorBindings(),
      ...this.woodFluxBindings(true),
      ...(this.usePressureCache?[[64,this.pressureSource]]:[]),
    ]);
    this.ci = 1 - ci;
    if (this.embers && !this.smoke) {
      const pass = encoder.beginComputePass();
      pass.setPipeline(this.emberPipeline);
      pass.setBindGroup(
        0,
        this.group(this.emberPipeline, [
          ...base,
          [2, this.v[vi]],
          [3, this.c[this.ci]],
          ...this.chemistryBindings(this.ci),
          [4, { buffer: this.emberBuffer }],
        ]),
      );
      pass.dispatchWorkgroups(32);
      pass.end();
    }
    this.stamp(encoder, index * 8 + 7);
    this.time += dt;
    this.burstAge += dt;
    this.powerCasts?.step(dt);
  }
  resetSurface(encoder) {
    if(this.reactionLedger)encoder.clearBuffer(this.reactionLedger,this.reactionOffset,this.D**3*4);
    this.updateObject();
    this.woodStructure?.reset();
    this.woodFlux?.reset(encoder);
    for (const skin of this.surface)
      this.dispatch(encoder, this.surfaceResetPipeline, [[14, skin]], 64);
    for (const damage of this.damage || [])
      this.dispatch(
        encoder,
        this.damageResetPipeline,
        [
          [13, { buffer: this.objectSettings }],
          [16, damage],
        ],
        64,
      );
  }
  objectBindings(state = false) {
    return [
      [11, this.objectModels[this.objectId] || this.emptyObject],
      ...(state ? [[12, this.surface[this.si]]] : []),
      [13, { buffer: this.objectSettings }],
      ...(this.woodCollision?.bindings()||[]),
    ];
  }
  woodPoseBindings(){return this.emptyWoodNodes||this.woodStructure?[[35,{buffer:this.woodStructure?.staticBuffer||this.emptyWoodNodes}],[36,{buffer:this.woodStructure?.state||this.emptyWoodPose}]]:[];}
  velocitySourceBindings(){return this.usePressureCache?[[64,this.pressureSource]]:[[61,{buffer:this.reactionLedger}]];}
  woodFluxBindings(packet=false){return [...(this.woodFlux?.bindings()||(this.emptyWoodFlux?[[34,{buffer:this.emptyWoodFlux}]]:[])),...(packet&&this.multirateWood?[[44,{buffer:this.woodPacket}]]:[])];}
  updateObject() {
    const tint = FIRE_COLORS.find((c) => c.id === this.color) || FIRE_COLORS[0];
    this.device.queue.writeBuffer(
      this.objectSettings,
      0,
      new Float32Array([
        ...this.source,
        this.effect[1],
        this.objectId ? 1 : 0,
        tint.id === 'natural' ? 0 : 1,
        // Negative options.z identifies a gas-only source for shared optics;
        // solid materials retain their positive ageing multiplier.
        this.objectId ? (this.woodTimeScale || 12) : (this.fuel === 0 ? -1 : 0),
        this.objectId ? (this.ignition || 0) : this.effect[0],
        ...tint.rgb,
        this.objectId === 'cybr-tree' ? (this.treeMoisture === 'damp' ? 2 : 1) : ({logs:-2,house:-3,'wood-sigil':-4}[this.objectId]||0),
      ]),
    );
  }
  camera(data) {
    data=[...data];data[11]=this.floorFuelKind===.35?1:0;
    this.cameraValues = data;
    const key = [...data.slice(16,23),...data.slice(24)].join(',');
    if (key !== this.lightKey) {
      this.lightKey = key;
      this.lightReady = false;
    }
    this.inspectSmoke = data[17] > 0.5;
    this.roomVisible = data[16] > 0.5;
    this.device.queue.writeBuffer(this.view, 0, new Float32Array(data));
  }
  render(encoder) {
    this.stamp(encoder, 100);
    if (this.usingTree) this.forestMesh.render(encoder);
    const pass = encoder.beginRenderPass({
      colorAttachments: [
        { view: this.outputView, clearValue: [0, 0, 0, 1], loadOp: 'clear', storeOp: 'store' },
      ],
    });
    pass.setPipeline(this.renderPipeline);
    pass.setBindGroup(
      0,
      this.group(this.renderPipeline, [
        [61,{buffer:this.reactionLedger}],
        [0, this.c[this.ci]],
        [1, this.sampler],
        [2, { buffer: this.view }],
        [3, this.light],
        ...(this.phaseLighting?[[48,this.phaseLight]]:[]),
        [5, { buffer: this.fireLights }],
        [6, this.roomTargets[0]],
        [7, this.roomTargets[1]],
        [9, { buffer: this.visibleBricks }],
        [31,this.sigilSource],
        ...this.floorBindings(true),
        ...this.objectBindings(true),
        ...this.meshBindings(),
        ...(this.damage?[[15, this.damage[this.si]]]:[]),
        ...this.meshShadowBindings(),
        ...this.chemistryBindings(this.ci,true),
      ]),
    );
    pass.draw(3);
    if (this.embers && !this.smoke && !this.inspectSmoke) {
      pass.setPipeline(this.emberRender);
      pass.setBindGroup(
        0,
        this.group(this.emberRender, [
          [0, { buffer: this.emberBuffer }],
          [1, { buffer: this.view }],
          [2, this.sampler],
          [3, this.c[this.ci]],
          [4, this.objectModels[this.objectId] || this.emptyObject],
          [5, { buffer: this.objectSettings }],
          ...(this.woodCollision?.bindings()||[]),
          ...this.chemistryBindings(this.ci),
        ]),
      );
      pass.draw(6, 2048);
    }
    pass.end();
    const present = encoder.beginRenderPass({
      colorAttachments: [
        { view: this.context.getCurrentTexture().createView(), loadOp: 'clear', storeOp: 'store' },
      ],
      ...(this.query ? { timestampWrites: { querySet: this.query, endOfPassWriteIndex: 101 } } : {}),
    });
    present.setPipeline(this.present);
    present.setBindGroup(0, this.group(this.present, [[0, this.outputView]]));
    present.draw(3);
    present.end();
  }
  async collectFluxTelemetry(slot,sampleFrame,epoch){
    try{
      await slot.fluxStatus.mapAsync(GPUMapMode.READ);
      if(this.destroyed||epoch!==this.stateEpoch)return;
      const values=new Uint32Array(slot.fluxStatus.getMappedRange());
      if(values[0]||values[1])throw Error('Unsafe conservative transport: '+JSON.stringify({sampleFrame,cflViolations:values[0],negativeConcentrations:values[1]}));
      this.latestTelemetry={...this.latestTelemetry,fluxSampleFrame:sampleFrame,fluxCflViolations:0,fluxNegativeConcentrations:0};
    }catch(error){if(!this.destroyed&&epoch===this.stateEpoch)this.errors.push(error.message||String(error));}
    finally{if(slot.fluxStatus.mapState==='mapped')slot.fluxStatus.unmap();slot.fluxPending=false;}
  }
  async collectShockTelemetry(slot,sampleFrame,epoch){
    try{
      await slot.shockStatus.mapAsync(GPUMapMode.READ);
      if(this.destroyed||epoch!==this.stateEpoch)return;
      const range=slot.shockStatus.getMappedRange();const f=new Float32Array(range);const u=new Uint32Array(range);
      this.latestTelemetry.shockSignal=f[4];this.latestTelemetry.shockRemaining=f[0];this.latestTelemetry.shockElapsed=f[2];
      if(u[3]!==0)throw Error('Compressible timestep validation failed: '+JSON.stringify({remaining:f[0],signal:f[4],flags:u[3]}));
    }catch(error){if(!this.destroyed&&epoch===this.stateEpoch)this.errors.push(error.message);}
    finally{if(slot.shockStatus.mapState==='mapped')slot.shockStatus.unmap();slot.shockPending=false;}
  }
  async collectTelemetry(slot, substeps, sampleFrame, epoch, dt, collectQuery = !!slot.query) {
    const sampledTime = this.time;
    const lightingRefresh = slot.lightingRefresh;
    let statsReleased = false;
    try {
      await slot.stats.mapAsync(GPUMapMode.READ);
      if (this.destroyed || epoch !== this.stateEpoch) return;
      const mapped = slot.stats.getMappedRange();
      const values = new Float32Array(mapped);
      const maxSpeed = values[0];
      if (!Number.isFinite(maxSpeed) || maxSpeed > 1000)
        throw Error('Invalid velocity state: ' + JSON.stringify({ time: sampledTime, sampleFrame, maxSpeed }));
      const diagnostic = {
        maxSpeed,projectionTime:sampledTime,projectionDt:dt/Math.max(substeps,1),projectionSampleFrame:sampleFrame,
        preDivergence: values[1] / Math.max(values[3], 1),
        postDivergence: values[2] / Math.max(values[3], 1),
      };
      if(this.adaptive&&mapped.byteLength>=32){const work=new Uint32Array(mapped,16,3);diagnostic.refinedFlowTiles=work[0];diagnostic.flowSparse=work[1]===1;diagnostic.flowStickyDense=work[2]===1;}
      slot.stats.unmap();
      slot.pending = false;
      statsReleased = true;
      if (!this.destroyed && epoch === this.stateEpoch && sampleFrame >= (this.latestTelemetry.sampleFrame || 0)) {
        this.latestTelemetry = { ...this.latestTelemetry, ...diagnostic, sampleFrame };
        if (dt > 0) this.maxSpeed = Math.max(maxSpeed, 0.1);
      }
      if (collectQuery) {
        try {
          await slot.query.mapAsync(GPUMapMode.READ);
          if (this.destroyed || epoch !== this.stateEpoch) return;
          const t = new BigUint64Array(slot.query.getMappedRange());
          const gpu = gpuCosts(t,substeps);
          slot.query.unmap();
          // Stats and timestamp mappings complete independently. Comparing a
          // timestamp against the newest *stats* frame discards valid GPU
          // timing whenever its query map finishes one display tick later.
          if (!this.destroyed && epoch === this.stateEpoch && sampleFrame >= (this.latestTelemetry.gpuSampleFrame || 0)) {
            if (lightingRefresh) this.lastLightingCostMs = gpu.lighting;
            this.latestTelemetry = { ...this.latestTelemetry, gpu, gpuSampleFrame: sampleFrame };
          }
        } catch (error) {
          // Timestamp queries are diagnostic. A failed map must not stop fire.
          if (!this.destroyed && epoch === this.stateEpoch) {
            this.queryTimingAvailable = false;
            this.lastLightingCostMs = null;
            this.latestTelemetry = { ...this.latestTelemetry, gpu: null };
          }
        }
      }
    } catch (error) {
      if (!this.destroyed && !this.lost && epoch === this.stateEpoch)
        this.errors.push(error?.message || String(error));
    } finally {
      if (!statsReleased) {
        if (slot.stats.mapState === 'mapped') slot.stats.unmap();
        slot.pending = false;
      }
      if (collectQuery) {
        if (slot.query.mapState === 'mapped') slot.query.unmap();
        slot.queryPending = false;
      }
    }
  }
  async collectPoolTelemetry(slot,sampleFrame,epoch) {
    try {
      await slot.poolStatus.mapAsync(GPUMapMode.READ);
      const status=Array.from(new Uint32Array(slot.poolStatus.getMappedRange(),0,8));
      slot.poolStatus.unmap();
      if (!this.destroyed && epoch===this.stateEpoch && sampleFrame >= (this.latestTelemetry.poolSampleFrame||0))
        this.latestTelemetry={...this.latestTelemetry,poolSampleFrame:sampleFrame,brickPool:{
          mode:status[0]===0?'sparse':'dense',requested:status[1],resident:status[2],allocated:status[3],
          free:status[4],overflow:status[5],epoch:status[6],migrationPending:status[7]!==0,
          capacity:this.chemistryPool.plan.capacity,
          additionalAtlasBytes:this.chemistryPool.plan.sharedStorage?0:this.chemistryPool.plan.atlasBytes,
          chemistryStorageBytes:this.chemistryPool.plan.atlasBytes+this.chemistryPool.plan.separateDenseBytes,
        }};
    } catch {
      this.poolTelemetryAvailable=false;
    } finally {
      if (slot.poolStatus.mapState==='mapped') slot.poolStatus.unmap();
      slot.poolPending=false;
    }
  }
  resolveTimings(encoder,slot,substeps){
    if(substeps>0){
      encoder.resolveQuerySet(this.query,0,substeps*8,this.queryResolve,0);
      encoder.copyBufferToBuffer(this.queryResolve,0,slot.query,0,substeps*64);
      encoder.resolveQuerySet(this.query,96,2,this.queryResolve,768);
      encoder.copyBufferToBuffer(this.queryResolve,768,slot.query,768,16);
    }
    encoder.resolveQuerySet(this.query,98,4,this.queryResolve,1024);
    encoder.copyBufferToBuffer(this.queryResolve,1024,slot.query,784,32);
  }
  canSubmit() {
    return this.inFlight.length < 2;
  }
  async frame(dt = 1 / 60, { waitForCapacity = true, realtimePacing = false } = {}) {
    if (this.lost) throw Error('GPU device lost: ' + this.lost);
    if (this.errors.length) throw Error(this.errors.at(-1));
    const shockWindow=(this.powerCasts?.slots||[]).some(c=>c.active&&c.definition?.blastWindows?.length&&c.age<=c.definition.duration&&c.age+dt>=c.definition.windup);
    if(shockWindow&&!this.shockStage)await this.ensureShockStage();
    const wall = performance.now();
    // Bound GPU work in flight without waiting for a CPU-visible map. Otherwise
    // a fast JS loop can queue seconds of simulation behind a busy adapter.
    if (!waitForCapacity && !this.canSubmit()) return null;
    while (!this.canSubmit())
      await gpuSessionTimeout(Promise.race(this.inFlight), 'frame completion', 8000);
    await this.prepareSource();
    this.updateObject();
    const encoder = this.device.createCommandEncoder();
    // Keep the completed chemistry source until flow consumes it next step.
    // The two-mask work halo writes zero records before a brick retires.
    encoder.clearBuffer(this.stats);
    if(this.fluxDiagnostics)encoder.clearBuffer(this.fluxDiagnostics);
    const telemetryLag = this.frameNumber - (this.latestTelemetry.sampleFrame || 0);
    const safeSpeed = Math.max(cflSafeSpeed(this.maxSpeed, telemetryLag, this.burstAge),
      this.active ? this.powerCasts?.speedFloor(dt)||0 : 0,
      woodIgnitionSpeedFloor(!!this.woodStructure,this.active,this.burstAge,this.objectId==='cybr-tree'));
    // Interactive catch-up is limited by the same physical CFL estimate.
    // Bound each submission, retain remaining wall-time debt in the app.
    if(realtimePacing)dt=Math.min(dt,4*((1.5*6)/this.N)/Math.max(safeSpeed,this.burstAge<.12?12:0,.0001));
    const substeps =
      dt > 0
        ? Math.max(
            1,
            Math.ceil(
              (dt * Math.max(safeSpeed, this.burstAge < 0.12 ? 12 : 0)) / ((1.5 * 6) / this.N),
            ),
          )
        : 0;
    if (substeps > 12)
      throw Error('CFL requires more than 12 steps; frame budget cannot safely be met.');
    // Empty timestamped passes bracket all simulation compute on the GPU timeline.
    this.stamp(encoder, 96);
    for (let i = 0; i < substeps; i++) this.step(encoder, dt / substeps, i, dt);
    // The solid collision field changes only with the wood pose. Rebuild it
    // once after the substeps, from the latest pose, instead of clearing and
    // voxelizing the full 128^3 field inside every fluid substep.
    if (substeps > 0 && this.woodCollision && this.objectId&&!this.geometryPressure?.enabled) this.woodCollision.encode(encoder);
    this.stamp(encoder, 97);
    this.stamp(encoder, 98);
    // Recomputing the full volume and room illumination every simulation tick
    // can dominate the GPU. Keep the full-resolution light solve, but reuse its
    // result for one frame when its measured cost exceeds 4 ms. Rig, camera,
    // source and material changes still force an immediate refresh.
    this.lightingAge=(this.lightingAge||0)+dt;
    const moved=this.lastLightingSource&&this.source.some((v,i)=>Math.abs(v-this.lastLightingSource[i])>6/this.D*.25);
    const transient=(this.powerCasts?.slots||[]).some(c=>c.active)||this.burstAge<.5;
    const relit=shouldRefreshLighting(dt,this.lightReady,this.frameNumber,this.lastLightingCostMs,{age:this.lightingAge,transient,moved});
    if(relit){this.lightingAge=0;this.lastLightingSource=[...this.source];}
    if (relit) {
      if (this.usingTree) this.forestMesh.shadows(encoder);
      this.dispatch(
        encoder,
        this.dilatePipeline,
        [
          [0, { buffer: this.opticalMasks[this.ci] }],
          [1, { buffer: this.visibleBricks }],
          ...(this.useLightReceivers ? [[2,{buffer:this.lightingReceivers}]] : []),
        ],
        32,
      );
      const gather = encoder.beginComputePass();
      gather.setPipeline(this.gatherPipeline);
      gather.setBindGroup(
        0,
        this.group(this.gatherPipeline, [
          [61,{buffer:this.reactionLedger}],
          [0, this.c[this.ci]],
          [1, this.sampler],
          [2, { buffer: this.view }],
          [5, { buffer: this.lightSeeds }],
          ...this.chemistryBindings(this.ci,true),
        ]),
      );
      gather.dispatchWorkgroups(8);
      gather.end();
      const refine = encoder.beginComputePass();
      refine.setPipeline(this.gatherAdaptivePipeline);
      refine.setBindGroup(
        0,
        this.group(this.gatherAdaptivePipeline, [
          [61,{buffer:this.reactionLedger}],
          [0, this.c[this.ci]],
          [1, this.sampler],
          [2, { buffer: this.view }],
          [5, { buffer: this.fireLights }],
          [10, { buffer: this.lightSeeds }],
          [13, { buffer: this.objectSettings }],
          ...this.chemistryBindings(this.ci,true),
        ]),
      );
      refine.dispatchWorkgroups(8);
      refine.end();
      if (this.roomVisible) {
        const direct = encoder.beginComputePass();
        direct.setPipeline(this.roomPipeline);
        direct.setBindGroup(
          0,
          this.group(this.roomPipeline, [
            [0, this.c[this.ci]],
            [1, this.sampler],
            [2, { buffer: this.view }],
            [5, { buffer: this.fireLights }],
            [8, this.roomTargets[0]],
            [9, { buffer: this.visibleBricks }],
            ...this.objectBindings(),
            ...this.meshShadowBindings(),
            ...this.chemistryBindings(this.ci,true),
          ]),
        );
        direct.dispatchWorkgroups(ROOM_SIZE*5/8, ROOM_SIZE/8);
        direct.end();
        const bounce = encoder.beginComputePass();
        bounce.setPipeline(this.bouncePipeline);
        bounce.setBindGroup(
          0,
          this.group(this.bouncePipeline, [
            [0, this.c[this.ci]],
            [1, this.sampler],
            [2, { buffer: this.view }],
            [6, this.roomTargets[0]],
            [8, this.roomTargets[1]],
            [9, { buffer: this.visibleBricks }],
            ...this.objectBindings(),
            ...this.chemistryBindings(this.ci,true),
          ]),
        );
        bounce.dispatchWorkgroups(ROOM_SIZE*5/8, ROOM_SIZE/8);
        bounce.end();
      }
      if (this.useLightWork) {
        recordLightingWork(encoder,this.lightingPipelines,this.lightingGroups);
        this.indirectRun(encoder,this.lightWorkPipeline,[
          [0,this.c[this.ci]],[1,this.sampler],[2,{buffer:this.view}],[4,this.light],...(this.phaseLighting?[[49,this.phaseLight]]:[]),
          [5,{buffer:this.fireLights}],[6,this.roomTargets[0]],[9,{buffer:this.visibleBricks}],
          ...this.objectBindings(),...this.meshShadowBindings(),
          ...this.chemistryBindings(this.ci,true),
          [26,{buffer:this.lightingWork.indices}],[27,{buffer:this.lightingWork.dispatch}],
        ],this.lightingWork.dispatch);
      } else {
      this.dispatch(
        encoder,
        this.useLightReceivers ? this.lightReceiverPipeline : this.lightPipeline,
        [
          [0, this.c[this.ci]],
          [1, this.sampler],
          [2, { buffer: this.view }],
          [4, this.light],
          ...(this.phaseLighting?[[49,this.phaseLight]]:[]),
          [5, { buffer: this.fireLights }],
          [6, this.roomTargets[0]],
          [9, { buffer: this.visibleBricks }],
          ...this.objectBindings(),
          ...this.meshShadowBindings(),
          ...this.chemistryBindings(this.ci,true),
          ...(this.useLightReceivers ? [[30,{buffer:this.lightingReceivers}]] : []),
        ],
        64,
      );
      }
      this.lightReady = true;
    }
    this.stamp(encoder, 99);
    this.render(encoder);
    const slot = this.telemetrySlots.find((candidate) => !candidate.pending&&!candidate.fluxPending&&!candidate.shockPending);
    if (slot) {
      slot.pending = true;
      slot.lightingRefresh = relit;
      encoder.copyBufferToBuffer(this.stats, 0, slot.stats, 0, 16);
      if(this.adaptive)encoder.copyBufferToBuffer(this.flowCommands,84,slot.stats,16,12);
    }
    const collectShock=!!slot?.shockStatus&&!slot.shockPending&&this.shockRemaining>0;
    if(collectShock){slot.shockPending=true;encoder.copyBufferToBuffer(this.shockStage.clock,0,slot.shockStatus,0,32);}
    const collectFlux=!!slot?.fluxStatus;
    if(collectFlux){slot.fluxPending=true;encoder.copyBufferToBuffer(this.fluxDiagnostics,0,slot.fluxStatus,0,16);}
    const collectPool=!!slot?.poolStatus&&!slot.poolPending&&this.poolTelemetryAvailable!==false;
    if (collectPool) {
      slot.poolPending=true;
      const source=this.chemistryPool.statusSource;
      encoder.copyBufferToBuffer(source.buffer,source.offset,slot.poolStatus,0,source.size);
    }
    const collectQuery = !!slot?.query && !slot.queryPending && this.queryTimingAvailable !== false;
    if (collectQuery) {
      slot.queryPending = true;
      this.resolveTimings(encoder, slot, substeps);
    }
    this.device.queue.submit([encoder.finish()]);
    const sampleFrame = ++this.frameNumber;
    if (slot) void this.collectTelemetry(slot, substeps, sampleFrame, this.stateEpoch, dt, collectQuery);
    if(collectShock)void this.collectShockTelemetry(slot,sampleFrame,this.stateEpoch);
    if(collectFlux)void this.collectFluxTelemetry(slot,sampleFrame,this.stateEpoch);
    if (collectPool) void this.collectPoolTelemetry(slot,sampleFrame,this.stateEpoch);
    const fence = this.device.queue.onSubmittedWorkDone();
    this.inFlight.push(fence);
    fence.then(
      () => { this.completedFrames++; this.inFlight = this.inFlight.filter((item) => item !== fence); },
      (error) => { this.inFlight = this.inFlight.filter((item) => item !== fence); if (!this.destroyed) this.errors.push(error?.message || String(error)); },
    );
    const diagnostic = this.latestTelemetry;
    const completedAt = performance.now();
    return {
      wall: completedAt - wall,
      startedAt: wall,
      completedAt,
      gpu: diagnostic.gpu,
      gpuTelemetryAge: diagnostic.gpu ? sampleFrame - (diagnostic.gpuSampleFrame || 0) : null,
      telemetryAge: sampleFrame - (diagnostic.sampleFrame || 0),
      completedFrames: this.completedFrames,
      relit,
      substeps,
      time: this.time,
      ...diagnostic,
    };
  }
  burst(at = this.source) {
    this.stateEpoch++;
    this.maxSpeed = Math.max(this.maxSpeed, 12);
    this.source = [...at];
    this.burstAge = 0;
    this.seed += 3.17;
    this.active = true;
  }
  castPower(at = this.source, direction = this.powerDirection, strength = this.powerStrength, options = {}) {
    const definition=this.selectedPower();
    if(!definition||!options||typeof options!=='object'||!at||at.length!==3||
      !direction||direction.length!==3||![...at,...direction,strength].every(Number.isFinite)||
      (options.target&&(!Array.isArray(options.target)||options.target.length!==3||!options.target.every(Number.isFinite))))return false;
    const length=Math.hypot(...direction);if(length<1e-8)return false;
    this.powerDirection=direction.map(v=>v/length);
    this.powerStrength=Math.max(.25,Math.min(2,strength));
    this.launchPowerDirection=[...this.powerDirection];
    this.launchPowerStrength=this.powerStrength;
    this.powerTrailLast=null;
    this.burst(at);this.previousDt=0;this.lightReady=false;
    const pool=this.powerCasts||(this.powerCasts=new PowerCastPool());
    pool.cast(definition,{origin:at,direction:this.powerDirection,target:options.target,
      strength:this.powerStrength,scale:this.effect[1],seed:this.seed,held:!!options.held});
    if(definition.blastWindows.length&&!this.shockStage)this.ensureShockStage().catch(error=>{this.shockError=error;});
    if(this.powerUsesFloorFuel(definition)){
      // A trail spends the existing finite floor inventory. A held stationary
      // cursor does not create an infinite reservoir or a second gas emitter.
      const point=[at[0],at[2]];
      if(this.depositPowerTrail(point)){this.powerTrailLast=point;this.igniteFuel();}
    }
    return true;
  }
  ensureShockStage(){
    if(this.shockStage)return Promise.resolve(this.shockStage);
    if(!this.shockInitPromise)this.shockInitPromise=new CompressibleShockStage(this.device,POWER_DEFINITIONS).init().then(stage=>{this.shockStage=stage;for(const slot of this.telemetrySlots){slot.shockStatus=this.device.createBuffer({size:32,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});slot.shockPending=false;this.resources.push(slot.shockStatus);}return stage;});
    return this.shockInitPromise;
  }
  movePower(at, direction = this.powerDirection, target = null) {
    // Projectiles and delayed bombs retain their launch origin after casting.
    // Rain, tornadoes and floor trails follow the held cursor without a reset.
    const definition=this.selectedPower();
    if(!definition?.continuous||definition.movable===false||!at||at.length!==3||
      !direction||direction.length!==3||![...at,...direction].every(Number.isFinite)||
      (target&&(!Array.isArray(target)||target.length!==3||!target.every(Number.isFinite))))return false;
    const length=Math.hypot(...direction);if(length<1e-8)return false;
    this.source=[...at];this.powerDirection=direction.map(v=>v/length);
    this.powerCasts?.move(at,target,{direction:this.powerDirection,strength:this.powerStrength,scale:this.effect[1]});
    this.previousDt=0;this.lightReady=false;
    if(this.powerUsesFloorFuel(definition)){
      const point=[at[0],at[2]];
      const changed=this.depositPowerTrail(point,this.powerTrailLast);
      if(changed){this.powerTrailLast=point;this.igniteFuel();}
      return changed;
    }
    this.stateEpoch++;this.maxSpeed=Math.max(this.maxSpeed,8);
    return true;
  }
  depositPowerTrail(point, previous = null) {
    // The power's authored dose does not overwrite the ordinary fuel-brush UI.
    const radius=this.fuelBrush.radius,amount=this.fuelBrush.amount;
    try{
      this.fuelBrush.radius=Math.max(.08,Math.min(.8,.26*this.effect[1]));
      this.fuelBrush.amount=.85*this.powerStrength;
      return this.dropFuel(point,previous);
    }finally{this.fuelBrush.radius=radius;this.fuelBrush.amount=amount;}
  }
  powerUniform() {
    // A projectile's launch settings are fixed. Aim controls affect the next
    // cast; ongoing rain, vortex and trail powers continue to follow controls.
    const definition=this.selectedPower();
    const transient=!!definition&&!definition.continuous;
    const direction=(transient&&this.launchPowerDirection)||this.powerDirection||authoredPowerDirection();
    const strength=transient&&this.launchPowerStrength!=null?this.launchPowerStrength:(this.powerStrength||1);
    return [...direction,strength];
  }
  selectedPower() {
    return powerDefinition(this.effect[0]-21);
  }
  powerUsesFloorFuel(definition=this.selectedPower()) {
    return definition?.floorFuel===true;
  }
  releasePower(target = null, direction = this.powerDirection) {
    if(!this.selectedPower()||!direction||direction.length!==3||!direction.every(Number.isFinite)||
      (target&&(!Array.isArray(target)||target.length!==3||!target.every(Number.isFinite))))return false;
    if(Math.hypot(...direction)<1e-8)return false;
    const released=this.powerCasts?.release(target,direction);
    if(released){this.previousDt=0;this.lightReady=false;this.maxSpeed=Math.max(this.maxSpeed,12);this.stateEpoch++;}
    return !!released;
  }
  aimPower(target, direction = this.powerDirection) {
    if(!target||target.length!==3||!target.every(Number.isFinite)||!direction||direction.length!==3||
      !direction.every(Number.isFinite)||Math.hypot(...direction)<1e-8)return false;
    return !!this.powerCasts?.aim(target,direction);
  }
  stopPower() {
    this.active=false;this.powerCasts?.stop();this.previousDt=0;this.lightReady=false;
  }
  cancelPower() {
    const cancelled=this.powerCasts?.cancelHeld();
    if(cancelled){this.stateEpoch++;this.previousDt=0;this.lightReady=false;}
    return !!cancelled;
  }
  async pixels() {
    const width = this.canvas.width, height = this.canvas.height;
    const row = width * 4;
    const paddedRow = Math.ceil(row / 256) * 256;
    const buffer = this.device.createBuffer({
      size: paddedRow * height,
      usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ,
    });
    try {
      const encoder = this.device.createCommandEncoder();
      encoder.copyTextureToBuffer({ texture: this.output }, { buffer, bytesPerRow: paddedRow }, [width,height]);
      this.device.queue.submit([encoder.finish()]);
      await buffer.mapAsync(GPUMapMode.READ);
      const mapped = new Uint8Array(buffer.getMappedRange());
      const bytes = new Uint8ClampedArray(row * height);
      for (let y = 0; y < height; y++)
        bytes.set(mapped.subarray(y * paddedRow, y * paddedRow + row), y * row);
      return bytes;
    } finally {
      if (buffer.mapState === 'mapped') buffer.unmap();
      buffer.destroy();
    }
  }
  resizeOutput(width, height) {
    if (this.canvas.width === width && this.canvas.height === height) return false;
    if (width < 1 || height < 1) throw Error('Invalid output dimensions.');
    const old = this.output;
    this.canvas.width = width;
    this.canvas.height = height;
    this.output = this.device.createTexture({
      size: [width, height],
      format: 'rgba8unorm',
      usage:
        GPUTextureUsage.RENDER_ATTACHMENT |
        GPUTextureUsage.TEXTURE_BINDING |
        GPUTextureUsage.COPY_SRC,
    });
    this.outputView = this.output.createView();
    this.forestMesh?.resizeOutput(width, height);
    this.resources.splice(this.resources.indexOf(old), 1, this.output);
    this.cache.clear();
    old.destroy();
    return true;
  }
  async drain() {
    await this.device.queue.onSubmittedWorkDone();
  }
  async reset() {
    this.stateEpoch++;
    await gpuSessionTimeout(this.device.queue.onSubmittedWorkDone(), 'reset drain', 8000);
    this.lightReady = false;
    this.previousDt = 0;
    this.time = 0;
    this.smokeDecayRemainder = 0;
    this.burstAge = 0;
    this.shockRemaining = 0;
    this.powerTrailLast = null;
    this.launchPowerDirection = null;
    this.launchPowerStrength = null;
    this.powerCasts?.reset();
    this.maxSpeed = 12;
    this.latestTelemetry = { maxSpeed: 12, preDivergence: 0, postDivergence: 0, gpu: null, sampleFrame: this.frameNumber };
    this.lastLightingCostMs = null;
    // Reset in place; no full-volume CPU uploads or transient half-GB buffers.
    const encoder = this.device.createCommandEncoder();
    if(this.materialFlow){this.materialIndex=0;for(const field of this.materialFlow)this.dispatch(encoder,this.materialClear,[[0,field]],64);}
    if (this.flowCommands) this.device.queue.writeBuffer(this.flowCommands,0,initialAdaptiveFlowCommands(this.N,this.D));
    encoder.clearBuffer(this.emberBuffer);
    this.chemistryPool?.encodeReset(encoder);
    this.clearFloorFuel(encoder);
    this.resetSurface(encoder);
    if(this.usePressureCache)this.dispatch(encoder,this.pressureSourceClear,[[0,this.pressureSource]],this.D/2);
    for (const mask of this.masks) encoder.clearBuffer(mask);
    for (const mask of this.opticalMasks) encoder.clearBuffer(mask);
    for (const fields of [this.v, this.c])
      this.dispatch(
        encoder,
        this.clearPipeline,
        fields.map((f, i) => [i, f]),
        fields[0].n,
      );
    this.device.queue.submit([encoder.finish()]);
    await gpuSessionTimeout(this.device.queue.onSubmittedWorkDone(), 'reset clear', 8000);
  }
  destroy() {
    this.geometryPressure?.destroy();this.powerContacts?.destroy();
    this.destroyed = true;
    this.adaptivePressure?.destroy();
    this.chemistryPool?.destroy();
    this.lightingWork?.destroy();
    this.lightingReceivers?.destroy();
    for(const buffer of [this.flowMask,this.flowTiles,this.flowCount,this.flowCommands,this.flowChemBricks,this.flowChemArgs]) buffer?.destroy();
    this.forestMesh?.destroy();
    this.woodStructure?.dispose();
    this.woodCollision?.dispose();
    this.woodFlux?.destroy();
    this.shockStage?.destroy();
    for (const r of this.resources) r.destroy();
    this.device.destroy();
  }
}
