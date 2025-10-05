import { ReactNode } from 'react';
import { SafeAreaView, View } from 'react-native';

export function Screen({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <SafeAreaView className="flex-1 bg-bg-light dark:bg-bg-dark">
      <View className={`flex-1 px-5 ${className ?? ''}`}>{children}</View>
    </SafeAreaView>
  );
}