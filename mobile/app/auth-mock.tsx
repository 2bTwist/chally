import { Screen } from '@/components/ui/Screen';
import { Text } from '@/components/ui/Text';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { View, Image } from 'react-native';
import { useState } from 'react';

export default function AuthMock() {
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');

  return (
    <Screen className="justify-center">
      <View className="items-center mb-8">
        <Image 
          source={require('@/assets/images/icon.png')} 
          style={{ width: 72, height: 72, borderRadius: 16 }} 
        />
        <Text variant="title" className="mt-3">Chally</Text>
        <Text variant="caption">Consistency through accountability</Text>
      </View>

      <Card>
        <Text variant="subtitle" className="mb-4">Sign in</Text>
        <Input 
          label="Email" 
          placeholder="you@example.com" 
          value={email} 
          onChangeText={setEmail} 
          className="mb-3" 
        />
        <Input 
          label="Password" 
          placeholder="••••••••" 
          secureTextEntry 
          value={pw} 
          onChangeText={setPw} 
          className="mb-4" 
        />
        <Button label="Continue" className="mb-3" />
        <Button label="Create account" variant="outline" />
      </Card>

      <View className="items-center mt-4">
        <Text variant="caption">By continuing you agree to our Terms & Privacy.</Text>
      </View>
    </Screen>
  );
}