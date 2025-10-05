import { forwardRef, useState } from 'react';
import { TextInput, TextInputProps, View } from 'react-native';
import { Text } from './Text';

type Props = TextInputProps & {
  label?: string;
  error?: string;
  className?: string;
};

export const Input = forwardRef<TextInput, Props>(function Input(
  { label, error, className, ...rest },
  ref
) {
  const [focused, setFocused] = useState(false);
  return (
    <View className={className}>
      {label ? <Text variant="caption" className="mb-1">{label}</Text> : null}
      <TextInput
        ref={ref}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        className={`rounded-xl px-4 py-3 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100
          border ${focused ? 'border-brand' : 'border-neutral-300 dark:border-neutral-700'}`}
        placeholderTextColor="#9ca3af"
        {...rest}
      />
      {error ? <Text variant="caption" className="text-red-600 mt-1">{error}</Text> : null}
    </View>
  );
});