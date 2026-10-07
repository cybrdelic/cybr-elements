// First 384 bytes remain the existing CPU-uploaded scene/cast ABI. The next
// 1152 bytes are GPU-resolved contact fractions and normals (six flights/cast).
export const SOLVER_PARAM_BYTES=1536;
export const solverParamsWGSL=`
struct PowerCast{originAge:vec4f,directionStrength:vec4f,kindScale:vec4f,targetCharge:vec4f};
struct ContactHit{hit:vec4f,timing:vec4f,point:vec4f};
struct CastContacts{hits:array<ContactHit,6>};
struct Params{step:vec4f,source:vec4f,shape:vec4f,effect:vec4f,dynamics:vec4f,chemistry:vec4f,lifecycle:vec4f,power:vec4f,casts:array<PowerCast,4>,contacts:array<CastContacts,4>};
`;
