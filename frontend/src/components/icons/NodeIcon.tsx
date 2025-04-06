import { SVGProps } from "react";

export function NodeIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...props} viewBox="0 0 256 292" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid">
      <defs>
        <linearGradient x1="68.188%" y1="17.487%" x2="27.823%" y2="89.755%" id="node-1">
          <stop stopColor="#41873F" offset="0%"/>
          <stop stopColor="#418B3D" offset="32.88%"/>
          <stop stopColor="#419637" offset="63.52%"/>
          <stop stopColor="#3FA92D" offset="93.19%"/>
          <stop stopColor="#3FAE2A" offset="100%"/>
        </linearGradient>
        <linearGradient x1="43.277%" y1="55.169%" x2="159.245%" y2="-18.306%" id="node-2">
          <stop stopColor="#41873F" offset="13.76%"/>
          <stop stopColor="#54A044" offset="40.32%"/>
          <stop stopColor="#66B848" offset="71.36%"/>
          <stop stopColor="#6CC04A" offset="90.81%"/>
        </linearGradient>
        <linearGradient x1="-4.389%" y1="49.997%" x2="101.499%" y2="49.997%" id="node-3">
          <stop stopColor="#6CC04A" offset="9.192%"/>
          <stop stopColor="#66B848" offset="28.64%"/>
          <stop stopColor="#54A044" offset="59.68%"/>
          <stop stopColor="#41873F" offset="86.24%"/>
        </linearGradient>
      </defs>
      <g>
        <path d="M134.923 1.832c-4.344-2.443-9.502-2.443-13.846 0L6.787 67.801C2.443 70.244 0 74.859 0 79.745v132.208c0 4.887 2.715 9.502 6.787 11.945l114.29 65.968c4.344 2.444 9.502 2.444 13.846 0l114.29-65.968c4.344-2.443 6.787-7.058 6.787-11.945V79.745c0-4.886-2.715-9.501-6.787-11.944l-114.29-65.969z" fill="url(#node-1)"/>
        <path d="M249.485 67.8L134.651 1.833c-1.086-.543-2.443-1.086-3.53-1.357L2.443 220.912c1.086 1.357 2.444 2.443 3.801 3.258l114.833 65.968c3.258 1.9 7.059 2.443 10.588 1.357l120.806-220.98c-.814-1.085-1.9-1.9-2.986-2.714z" fill="url(#node-2)"/>
        <path d="M249.756 223.898c3.258-1.9 5.701-5.158 6.787-8.687L130.58.204c-3.258-.543-6.787-.272-9.773 1.628L6.787 67.53l122.978 224.238c1.628-.272 3.53-.814 5.158-1.629l114.833-66.24z" fill="url(#node-3)"/>
      </g>
    </svg>
  );
}
