<template>
  <split-menu :model-value="15">
    <template #menu>
      <v-list nav density="compact">
        <v-list-item-title class="text-h6 pl-2 mb-2">User Profile</v-list-item-title>

        <v-list-item
          to="/users/self/" exact
          prepend-icon="mdi-account"
          title="User Information"
        />
        <v-list-item
          v-if="apiSettings.isLocalUserAuthEnabled"
          to="/users/self/security/"
          prepend-icon="mdi-lock"
          title="Security"
        />
        <v-list-item
          to="/users/self/apitokens/"
          prepend-icon="mdi-key-variant"
          title="API Tokens"
        />
        <v-list-item
          v-if="apiSettings.settings!.features.archiving"
          to="/users/self/publickeys/"
          prepend-icon="mdi-folder-key"
          title="Archiving Public Keys"
        />
      </v-list>
    </template>

    <template #default>
      <nuxt-page />
    </template>
  </split-menu>
</template>

<script setup lang="ts">
import { profileTitleTemplate } from "~/utils/title";

const route = useRoute();
useHead({
  titleTemplate: (title?: string|null) => profileTitleTemplate(title, route),
});
const apiSettings = useApiSettings();
</script>
