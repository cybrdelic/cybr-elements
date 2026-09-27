/* Shared optical coefficients: the flame, smoke and room see the same live
 * emission. This is an artistic combustion model, not calibrated spectroscopy. */
window.FireOptics = `
  const vec3 fireExtent=vec3(14.,7.875,1.8);
  const vec3 fireMin=vec3(-7.,-1.05,-.9);
  float sootExtinction(float soot){return max(soot,0.)*6.4;}
  vec3 fireEmission(float reaction,float temperature){
    float hot=clamp((temperature-.24)/2.0,0.,1.);
    vec3 spectrum=vec3(1.,.055+.78*pow(hot,1.6),.003+.36*pow(hot,3.8));
    return spectrum*pow(max(reaction,0.),1.08)*5.4;
  }
`;
