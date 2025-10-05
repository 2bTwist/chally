import { View, ViewProps } from 'react-native';

export function Card({ className, ...rest }: ViewProps & { className?: string }) {
  return <View {...rest} className={`rounded-2xl bg-white dark:bg-neutral-900 p-4 shadow ${className ?? ''}`} />;
}