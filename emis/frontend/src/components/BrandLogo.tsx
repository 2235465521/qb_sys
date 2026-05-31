import React from 'react';

interface BrandLogoProps {
  width?: number | string;
  height?: number | string;
  style?: React.CSSProperties;
}

const BrandLogo: React.FC<BrandLogoProps> = ({ width = 64, height = 64, style }) => {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ display: 'inline-block', verticalAlign: 'middle', ...style }}
    >
      {/* Back Document (Black fill with white border) */}
      <path
        d="M22 40 L22 85 A3 3 0 0 0 25 88 L62 88 A3 3 0 0 0 65 85 L65 52 L53 40 Z"
        fill="#141414"
        stroke="#ffffff"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M53 40 L53 52 L65 52 Z"
        fill="#ffffff"
        stroke="#ffffff"
        strokeWidth="1"
        strokeLinejoin="round"
      />

      {/* Front Document (White fill with black border) */}
      <path
        d="M35 25 L35 72 A3 3 0 0 0 38 75 L75 75 A3 3 0 0 0 78 72 L78 39 L65 25 Z"
        fill="#ffffff"
        stroke="#141414"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M65 25 L65 39 L78 39 Z"
        fill="#e8e8e8"
        stroke="#141414"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />

      {/* Green Upward Arrow */}
      <path
        d="M46 92 L46 32 L38 32 L50 14 L62 32 L54 32 L54 92 Z"
        fill="#52c41a"
        stroke="#3f9e11"
        strokeWidth="1"
        strokeLinejoin="round"
      />

      {/* Green Sparkle/Star at Tip */}
      <polygon
        points="50 0, 52.5 5, 58 5, 53.5 9, 55 14, 50 11, 45 14, 46.5 9, 42 5, 47.5 5"
        fill="#52c41a"
        stroke="#3f9e11"
        strokeWidth="0.5"
      />
    </svg>
  );
};

export default BrandLogo;
