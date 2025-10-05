import { ActivityIndicator, Pressable, PressableProps } from 'react-native';
import { Text } from './Text';

type Variant = 'primary' | 'outline' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

type ButtonProps = PressableProps & {
  label: string;
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  className?: string;
};

const sizeMap: Record<Size, string> = {
  sm: 'px-3 py-2 text-sm',
  md: 'px-4 py-3 text-base',
  lg: 'px-5 py-4 text-lg',
};

export function Button({ label, variant = 'primary', size = 'md', loading, className, disabled, ...rest }: ButtonProps) {
  const base =
    variant === 'primary'
      ? 'bg-brand rounded-xl'
      : variant === 'danger'
      ? 'bg-red-600 rounded-xl'
      : variant === 'outline'
      ? 'border border-neutral-300 dark:border-neutral-700 rounded-xl'
      : 'rounded-xl';

  const text =
    variant === 'primary' || variant === 'danger'
      ? 'text-white'
      : 'text-neutral-900 dark:text-neutral-100';

  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled || loading}
      className={`flex-row items-center justify-center ${sizeMap[size]} ${base} ${disabled || loading ? 'opacity-60' : ''} ${className ?? ''}`}
      {...rest}
    >
      {loading ? <ActivityIndicator /> : <Text className={`${text} font-semibold`}>{label}</Text>}
    </Pressable>
  );
}