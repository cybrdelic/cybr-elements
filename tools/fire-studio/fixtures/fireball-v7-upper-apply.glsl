#version 300 es
precision highp float;precision highp int;precision highp sampler2D;
   const int M=383,R=333;const vec2 K=vec2(2304,2304);layout(location=0)out vec4 result;
   int region(ivec2 c){return (c.x==M?2:0)+(c.y==R?1:0);}
   float value(sampler2D tex,ivec2 c,int block){
    if(block==3)return 0.;
    if(block==1){if(c.x<0||c.x>=M)return 0.;c.y=R;}
    else if(block==2){if(c.y>=R)return 0.;c=ivec2(M,max(c.y,0));}
    else {c.y=max(c.y,0);if(c.x<0||c.x>=M||c.y>=R)return 0.;}
    return texelFetch(tex,c,0).r;
   }
   float diagonal(ivec2 c){return (c.x<M?2.*K.x:0.)+(c.y<R?(c.y==0?K.y:2.*K.y):0.);}
   float operatorA(sampler2D tex,ivec2 c){int block=region(c);float p=value(tex,c,block),a=0.;
    if(c.x<M)a+=K.x*(2.*p-value(tex,c-ivec2(1,0),block)-value(tex,c+ivec2(1,0),block));
    if(c.y<R)a+=K.y*(2.*p-value(tex,c-ivec2(0,1),block)-value(tex,c+ivec2(0,1),block));return a;
   }const int FLOOR=50;const ivec2 OFFSET=ivec2(2688,2688);
    vec4 upper(sampler2D tex,ivec2 c){return texelFetch(tex,OFFSET+clamp(c,ivec2(0),ivec2(383,383)),0);}uniform sampler2D uProjected,uP;
    float xPhi(ivec2 c){return c.x<0||c.x>=M?0.:texelFetch(uP,c,0).r;}
    float yPhi(ivec2 c){return c.y<0||c.y>=R?0.:texelFetch(uP,c,0).r;}
    void main(){ivec2 xy=ivec2(gl_FragCoord.xy);vec4 v=upper(uProjected,xy);if(xy.y<FLOOR){result=v;return;}
     ivec2 c=xy-ivec2(0,FLOOR);v.x+=6*(xPhi(c-ivec2(1,0))-xPhi(c));
     if(c.y>0)v.y+=6*(yPhi(c-ivec2(0,1))-yPhi(c));result=v;
    }