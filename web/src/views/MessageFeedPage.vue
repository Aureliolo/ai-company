<script setup lang="ts">
import { onMounted, watch } from 'vue'
import AppShell from '@/components/layout/AppShell.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import ErrorBoundary from '@/components/common/ErrorBoundary.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import MessageList from '@/components/messages/MessageList.vue'
import ChannelSelector from '@/components/messages/ChannelSelector.vue'
import { useMessageStore } from '@/stores/messages'
import { sanitizeForLog } from '@/utils/logging'
import { useWebSocketSubscription } from '@/composables/useWebSocketSubscription'

const messageStore = useMessageStore()

useWebSocketSubscription({
  bindings: [{ channel: 'messages', handler: messageStore.handleWsEvent }],
})

onMounted(async () => {
  try {
    await Promise.all([messageStore.fetchChannels(), messageStore.fetchMessages()])
  } catch (err) {
    console.error('Initial data fetch failed:', sanitizeForLog(err))
  }
})

watch(
  () => messageStore.activeChannel,
  async (channel) => {
    try {
      await messageStore.fetchMessages(channel ?? undefined)
    } catch (err) {
      console.error('Channel message fetch failed:', sanitizeForLog(err))
    }
  },
)

function handleChannelChange(channel: string | null) {
  messageStore.setActiveChannel(channel)
}
</script>

<template>
  <AppShell>
    <PageHeader title="Messages" subtitle="Real-time communication feed">
      <template #actions>
        <ChannelSelector
          :model-value="messageStore.activeChannel"
          :channels="messageStore.channels"
          @update:model-value="handleChannelChange"
        />
      </template>
    </PageHeader>

    <ErrorBoundary :error="messageStore.error" @retry="() => messageStore.fetchMessages(messageStore.activeChannel ?? undefined)">
      <LoadingSkeleton v-if="messageStore.loading && messageStore.messages.length === 0" :lines="6" />
      <EmptyState
        v-else-if="messageStore.messages.length === 0"
        icon="pi pi-comments"
        title="No messages"
        message="Messages from agents will appear here in real-time."
      />
      <MessageList v-else :messages="messageStore.messages" />
    </ErrorBoundary>
  </AppShell>
</template>
