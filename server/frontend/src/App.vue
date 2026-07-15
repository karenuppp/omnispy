<script setup lang="ts">
import { darkTheme, zhCN, dateZhCN, NConfigProvider, NMessageProvider } from 'naive-ui'
import SideBar from './components/SideBar.vue'

const themeOverrides = {
  common: {
    bodyColor: '#0b0b0f',
    cardColor: '#131317',
    modalColor: '#131317',
    tableColor: '#0b0b0f',
    inputColor: '#1a1a1f',
    inputColorFocus: '#1a1a1f',
    borderColor: '#1f1f25',
    primaryColor: '#22d3a0',
    primaryColorHover: '#5eead4',
    primaryColorPressed: '#14b88c',
    primaryColorSuppl: '#22d3a0',
    textColor1: '#eaeaef',
    textColor2: '#88889a',
    textColor3: '#5c5c6e',
    placeholderColor: '#5c5c6e',
    placeholderColorDisabled: '#3a3a44',
    fontSize: '14px',
    fontSizeSmall: '12px',
    fontSizeTiny: '11px',
    borderRadius: '8px',
    borderRadiusSmall: '6px',
    popoverColor: '#1a1a1f',
    actionColor: '#131317',
    dividerColor: '#1f1f25',
    closeColor: '#5c5c6e',
    closeColorHover: '#eaeaef',
    clearColor: '#5c5c6e',
    clearColorHover: '#eaeaef',
    scrollbarColor: 'rgba(255, 255, 255, 0.06)',
    scrollbarColorHover: 'rgba(255, 255, 255, 0.12)',
    progressRailColor: '#1f1f25',
    railColor: '#1f1f25',
    fontWeight: '400',
    fontWeightStrong: '600',
    tagColor: '#1a1a1f',
    avatarColor: '#1a1a1f',
    opacity1: '0.04',
    opacity2: '0.08',
    opacity3: '0.12',
    opacity4: '0.16',
    opacity5: '0.2',
  },
  Button: {
    textColor: '#eaeaef',
    textColorPrimary: '#0b0b0f',
    border: '1px solid #1f1f25',
    borderHover: '1px solid #2a2a30',
    borderPressed: '1px solid #1f1f25',
    colorHover: 'rgba(255,255,255,0.04)',
    colorPressed: 'rgba(255,255,255,0.08)',
    colorPrimary: '#22d3a0',
    colorHoverPrimary: '#5eead4',
    colorPressedPrimary: '#14b88c',
    fontWeight: '500',
  },
  Card: {
    borderColor: '#1f1f25',
    colorEmbedded: '#0b0b0f',
    paddingSmall: '16px 20px',
    paddingMedium: '20px 24px',
    paddingLarge: '24px 28px',
    titleFontWeight: '600',
  },
  DataTable: {
    borderColor: '#1f1f25',
    tdColor: '#131317',
    thColor: '#0f0f13',
    thTextColor: '#88889a',
    tdTextColor: '#eaeaef',
    thFontWeight: '500',
    tdFontWeight: '400',
    thPaddingSmall: '10px 16px',
    tdPaddingSmall: '10px 16px',
  },
  Tag: {
    borderRadius: '6px',
    fontWeight: '500',
  },
  Input: {
    border: '1px solid #1f1f25',
    borderHover: '1px solid #2a2a30',
    borderFocus: '1px solid #22d3a0',
    color: '#1a1a1f',
    textColor: '#eaeaef',
  },
  Select: {
    menuColor: '#1a1a1f',
    menuBorderColor: '#1f1f25',
    menuBoxShadow: 'none',
    menuHeight: '220px',
  },
  Tabs: {
    tabTextColor: '#88889a',
    tabTextColorActive: '#22d3a0',
    tabTextColorHover: '#eaeaef',
    barColor: '#22d3a0',
    tabFontWeight: '500',
    tabFontWeightActive: '600',
  },
  Pagination: {
    itemTextColor: '#88889a',
    itemTextColorActive: '#22d3a0',
    itemColorActive: 'rgba(34,211,160,0.1)',
    buttonBorder: '1px solid #1f1f25',
    buttonBorderHover: '1px solid #2a2a30',
  },
  Popover: {
    color: '#1a1a1f',
    border: '1px solid #1f1f25',
    boxShadow: 'none',
  },
  Modal: {
    color: '#131317',
    borderColor: '#1f1f25',
    boxShadow: 'none',
  },
  Message: {
    color: '#1a1a1f',
    border: '1px solid #1f1f25',
    boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
  },
  Empty: {
    textColor: '#5c5c6e',
    iconColor: '#3a3a44',
  },
  Spin: {
    color: '#22d3a0',
  },
  Tooltip: {
    color: '#1a1a1f',
    border: '1px solid #1f1f25',
    boxShadow: 'none',
  },
}
</script>

<template>
  <NConfigProvider :theme="darkTheme" :theme-overrides="themeOverrides" :locale="zhCN" :date-locale="dateZhCN">
    <NMessageProvider>
      <div class="app-layout">
        <SideBar />
        <main class="app-main">
          <router-view />
        </main>
      </div>
    </NMessageProvider>
  </NConfigProvider>
</template>

<style>
*,
*::before,
*::after {
  box-sizing: border-box;
}

html, body, #app {
  margin: 0;
  padding: 0;
  min-height: 100%;
  background: #0b0b0f;
  color: #eaeaef;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  line-height: 1.5;
}

.app-layout {
  display: flex;
  min-height: 100vh;
}

.app-main {
  flex: 1;
  margin-left: 220px;
  padding: 32px 40px;
}

/* Scrollbar */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.1);
}

/* Naive UI overrides */
.n-card {
  box-shadow: none !important;
}

.n-card > .n-card-header {
  padding-bottom: 12px !important;
}

.n-data-table .n-data-table-tr {
  transition: background 0.12s ease;
}

.n-data-table .n-data-table-tr:hover {
  background: rgba(255, 255, 255, 0.02) !important;
}
</style>
