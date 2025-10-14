import { useEffect, useState } from 'react';
import { Screen } from '@/components/ui/Screen';
import { Text } from '@/components/ui/Text';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { fetchHealth } from '@/lib/api';

export default function HealthScreen() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    setErr(null);
    try {
      const h = await fetchHealth();
      setData(h);
    } catch (e: any) {
      setErr(e?.message ?? 'Unknown error');
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    run();
  }, []);

  return (
    <Screen className="py-6">
      <Text variant="title" className="mb-4">API Health</Text>

      <Card className="mb-4">
        <Button label="Refresh" onPress={run} loading={loading} />
      </Card>

      {err ? (
        <Card className="mb-4">
          <Text className="text-red-600">Error: {err}</Text>
        </Card>
      ) : null}

      {data ? (
        <Card>
          <Text>status: {data.status}</Text>
          <Text>env: {data.env}</Text>
          <Text>time: {data.time}</Text>
          <Text>request_id: {data.request_id}</Text>
        </Card>
      ) : null}
    </Screen>
  );
}