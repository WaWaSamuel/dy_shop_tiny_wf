type StickerIconProps = {
  src: string;
  alt: string;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
};

export default function StickerIcon({
  src,
  alt,
  size = 'md',
  className = '',
}: StickerIconProps) {
  return (
    <img
      src={src}
      alt={alt}
      className={`sticker-icon sticker-icon--${size}${className ? ` ${className}` : ''}`}
    />
  );
}
