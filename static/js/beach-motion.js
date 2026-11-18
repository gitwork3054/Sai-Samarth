(function () {
  'use strict';
  var imageUrl = document.currentScript.getAttribute('data-beach-src');
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (reduced.matches) return;
  var canvas = document.createElement('canvas');
  canvas.className = 'beach-motion';
  canvas.setAttribute('aria-hidden', 'true');
  var gl = canvas.getContext('webgl', { alpha: false, antialias: false, powerPreference: 'low-power' });
  if (!gl) return;
  var vertex = 'attribute vec2 p; varying vec2 v; void main(){v=p*.5+.5;gl_Position=vec4(p,0.,1.);}';
  var fragment = [
    'precision mediump float;',
    'uniform sampler2D photo; uniform vec2 viewport; uniform vec2 imageSize; uniform float time; varying vec2 v;',
    'void main(){',
    ' vec2 uv=vec2(v.x,1.0-v.y);',
    ' float a=viewport.x/viewport.y; float b=imageSize.x/imageSize.y;',
    ' if(a>b){uv.y=(uv.y-.5)*b/a+.5;}else{uv.x=(uv.x-.5)*a/b+.5;}',
    ' vec4 base=texture2D(photo,uv);',
    ' float water=smoothstep(.48,.59,uv.y)*(1.0-smoothstep(.72,.90,uv.x));',
    ' water*=smoothstep(.12,.34,dot(base.rgb,vec3(.299,.587,.114)));',
    ' vec2 ripple=vec2(sin(uv.y*80.0-time*.65+sin(uv.x*15.0+time*.24))*0.0022, sin(uv.x*38.0+uv.y*32.0-time*.52)*0.0014)*water;',
    ' vec3 col=texture2D(photo,clamp(uv+ripple,0.0,1.0)).rgb;',
    ' vec2 sun=(uv-vec2(.486,.427))*vec2(1.5,1.0); float d=length(sun);',
    ' float rays=pow(max(0.0,cos(atan(sun.y,sun.x)*9.0+time*.025)),18.0)*exp(-d*11.0)*smoothstep(.30,.44,uv.y);',
    ' col+=vec3(1.0,.53,.16)*rays*.13;',
    ' col=mix(col,vec3(.031,.086,.106),mix(.30,.34,uv.y));',
    ' gl_FragColor=vec4(col,1.0); }'
  ].join('\n');
  function shader(type, source) { var s=gl.createShader(type); gl.shaderSource(s,source); gl.compileShader(s); if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)) return null; return s; }
  var vs=shader(gl.VERTEX_SHADER,vertex), fs=shader(gl.FRAGMENT_SHADER,fragment);
  if(!vs || !fs) return;
  var program=gl.createProgram(); gl.attachShader(program,vs); gl.attachShader(program,fs); gl.linkProgram(program);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS)) return;
  gl.useProgram(program);
  var buffer=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,buffer); gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);
  var position=gl.getAttribLocation(program,'p'); gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
  var img=new Image();
  img.onload=function(){
    var texture=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,texture); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR); gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,img);
    gl.uniform2f(gl.getUniformLocation(program,'imageSize'),img.width,img.height);
    document.body.insertBefore(canvas,document.body.firstChild);
    var start=performance.now(), frame=0;
    function paint(now){
      if(document.hidden || reduced.matches){frame=0;return;}
      var ratio=Math.min(window.devicePixelRatio||1,1.25), w=Math.round(window.innerWidth*ratio), h=Math.round(window.innerHeight*ratio);
      if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h);}
      gl.uniform2f(gl.getUniformLocation(program,'viewport'),w,h);
      gl.uniform1f(gl.getUniformLocation(program,'time'),(now-start)/1000);
      gl.drawArrays(gl.TRIANGLE_STRIP,0,4); frame=requestAnimationFrame(paint);
    }
    function resume(){if(!frame&&!document.hidden&&!reduced.matches) frame=requestAnimationFrame(paint);}
    document.addEventListener('visibilitychange',resume);
    if(reduced.addEventListener) reduced.addEventListener('change',function(){if(reduced.matches){canvas.style.display='none';}else{canvas.style.display='';resume();}});
    canvas.addEventListener('webglcontextlost',function(e){e.preventDefault();canvas.remove();if(frame)cancelAnimationFrame(frame);});
    resume();
  };
  img.src=imageUrl;
})();
