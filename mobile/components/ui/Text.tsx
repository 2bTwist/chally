import { Text as RNText, TextProps } from 'react-native';

type TProps = TextProps & { variant?: 'title' | 'subtitle' | 'body' | 'caption'; className?: string };

export function Text({ variant = 'body', className, style, ...rest }: TProps) {
  const base =
    variant === 'title'
      ? 'text-2xl font-bold'
      : variant === 'subtitle'
      ? 'text-lg font-semibold text-neutral-700 dark:text-neutral-200'
      : variant === 'caption'
      ? 'text-xs text-neutral-500 dark:text-neutral-400'
      : 'text-base text-neutral-900 dark:text-neutral-100';

  return <RNText {...rest} style={style} className={`${base} ${className ?? ''}`} />;
}