import { Card } from '@/components/ui/Card';
import { Screen } from '@/components/ui/Screen';
import { Text } from '@/components/ui/Text';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useState } from 'react';
import { ScrollView, View } from 'react-native';
import { Link, router } from 'expo-router';

export default function DSGallery() {
  const [email, setEmail] = useState('');
  return (
    <Screen>
      <ScrollView contentContainerStyle={{ paddingVertical: 20 }}>
        <Text variant="title" className="mb-4">Design System</Text>
        
        {/* Navigation Card */}
        <Card className="mb-4">
          <Text variant="subtitle" className="mb-3">Navigation</Text>
          <View className="flex-row gap-3 flex-wrap">
            <Button 
              label="Auth Mock" 
              variant="outline"
              onPress={() => router.push('/auth-mock')}
            />
            <Button 
              label="Home Tabs" 
              variant="outline"
              onPress={() => router.push('/(tabs)')}
            />
            <Link href="/auth-mock" asChild>
              <Button label="Link to Auth" variant="ghost" />
            </Link>
          </View>
        </Card>
        <Card className="mb-4">
          <Text variant="subtitle" className="mb-3">Buttons</Text>
          <View className="flex-row gap-3">
            <Button label="Primary" />
            <Button label="Outline" variant="outline" />
            <Button label="Danger" variant="danger" />
            <Button label="Loading" loading />
          </View>
        </Card>
        <Card className="mb-4">
          <Text variant="subtitle" className="mb-3">Inputs</Text>
          <Input label="Email" placeholder="you@example.com" value={email} onChangeText={setEmail} className="mb-3" />
          <Input label="Password" placeholder="••••••••" secureTextEntry />
        </Card>
        <Card>
          <Text variant="subtitle" className="mb-2">Typography</Text>
          <Text variant="title">Title</Text>
          <Text variant="subtitle">Subtitle</Text>
          <Text>Body text looks like this.</Text>
          <Text variant="caption">Caption</Text>
        </Card>
      </ScrollView>
    </Screen>
  );
}