/* Shared optical coefficients: the flame, smoke and room see the same live
 * emission. This is an artistic combustion model, not calibrated spectroscopy. */
window.createFireOptics = () => `
  uniform float gasFlame;
  uniform vec3 flameTint;
  uniform float tintStrength;
  const vec3 fireExtent=${window.FireDomain?.extentGLSL||"vec3(14.,7.875,1.8)"};
  const vec3 fireMin=${window.FireDomain?.minimumGLSL||"vec3(-7.,-1.05,-.9)"};
  const float domainBlast=${window.FireDomain?.blast?"1.":"0."};
  float sootExtinction(float soot){return max(soot,0.)*4.4;}
  vec3 sootEmission(float soot,float temperature){
    float heat=max(temperature-.65,0.);
    return vec3(1.,.12,.015)*max(soot,0.)*heat*heat*.30;
  }
  vec3 fireEmission(float reaction,float temperature){
    float hot=clamp((temperature-.28)/1.8,0.,1.);
    vec3 spectrum=vec3(1.,.035+.93*pow(hot,1.3),.002+.72*pow(hot,3.0));
    spectrum=mix(spectrum,mix(vec3(.035,.20,1.),vec3(.38,.70,1.),hot),gasFlame);
    spectrum=mix(spectrum,mix(flameTint,vec3(1.),hot*.45),tintStrength);
    return spectrum*pow(max(reaction,0.),.95)*6.5;
  }
`;

window.FireOptics=window.createFireOptics();
