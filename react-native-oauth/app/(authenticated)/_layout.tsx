import { Stack } from 'expo-router'
import { ClientProvider } from '@/components/ClientProvider'

export default function AuthenticatedLayout() {
  return (
    <ClientProvider>
      <Stack screenOptions={{ headerShown: false }} />
    </ClientProvider>
  )
}
