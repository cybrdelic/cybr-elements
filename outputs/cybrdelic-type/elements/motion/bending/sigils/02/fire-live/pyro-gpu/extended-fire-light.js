// Deterministic quadrature for a finite emitting cluster. Distant receivers
// use the centroid; close receivers see the cluster's measured dimensions.
// Shadow rays remain one per cluster in smoke and four only on near surfaces.
export const extendedFireLightWGSL=`
fn clusterIncident(at:vec3f,normal:vec3f,surface:bool,index:u32)->vec4f{
 let light=lights[index];let center=light.position.xyz;let d=center-at;
 let r2=max(dot(d,d),.001);let span=max(light.upper.xyz-light.lower.xyz,vec3f(.015));
 let near=r2<dot(span,span)*4.;
 if(!near){let cosine=select(1.,max(dot(normal,d*inverseSqrt(r2)),0.),surface);
  return vec4f(light.power.xyz*cosine/(r2+max(.08,light.position.w))*shadow(at,center),0.);
 }
 var result=vec3f(0);let spread=span*.288675135;
 var commonShadow=1.;if(!surface){commonShadow=shadow(at,center);}
 for(var sample=0u;sample<4u;sample++){
  let signs=select(select(vec3f(-1,1,-1),vec3f(1,-1,-1),sample==2u),select(vec3f(-1,-1,1),vec3f(1,1,1),sample==0u),sample<2u);
  let point=clamp(center+signs*spread,light.lower.xyz,light.upper.xyz);
  let delta=point-at;let distance=max(dot(delta,delta),.001);
  let cosine=select(1.,max(dot(normal,delta*inverseSqrt(distance)),0.),surface);
  var visibility=commonShadow;if(surface){visibility=shadow(at,point);}
  result+=light.power.xyz*(.25*cosine*visibility)/(distance+.015);
 }
 return vec4f(result,1.);
}
`;
