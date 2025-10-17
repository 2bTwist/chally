export const tokens = {
  color: {
    brand: '#2f95dc',
    brandDark: '#1b6ea8',
    text: { light: '#111827', dark: '#F5F5F5' },
    muted: { light: '#6B7280', dark: '#9CA3AF' },
    surface: { light: '#ffffff', dark: '#111111' },
    border: { light: '#e5e7eb', dark: '#374151' },
  },
  radius: { md: 14, lg: 20 },
  spacing: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 },
} as const;

export type Tokens = typeof tokens;
