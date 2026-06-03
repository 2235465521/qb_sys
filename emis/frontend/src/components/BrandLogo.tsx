import React from 'react';
import logoImg from '@/assets/logo.jpg';

interface BrandLogoProps {
  width?: number | string;
  height?: number | string;
  style?: React.CSSProperties;
}

const BrandLogo: React.FC<BrandLogoProps> = ({ width = 64, height = 64, style }) => {
  return (
    <img
      src={logoImg}
      alt="Brand Logo"
      style={{
        width: width,
        height: height,
        borderRadius: '50%',
        objectFit: 'cover',
        display: 'inline-block',
        verticalAlign: 'middle',
        border: '1px solid #f0f0f0', // Subtle border to make it pop
        ...style
      }}
    />
  );
};

export default BrandLogo;
