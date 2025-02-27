<template>
  <div>
    <s-dialog v-model="reauthDialogVisible">
      <template #title>Re-Authentication required</template>
      <template #default>
        <v-card-text>
          This operation requires a re-authentication.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <s-btn
            @click="reauthDialogVisible = false"
            variant="text"
            text="Cancel"
          />
          <s-btn
            @click="auth.redirectToReAuth()"
            color="primary"
            text="Re-Authenticate"
          />
        </v-card-actions>
      </template>
    </s-dialog>

    <s-card class="mt-4">
      <v-card-title>API Tokens</v-card-title>
      <v-card-text>
        <v-list>
          <v-list-item
            v-for="apiToken in apiTokens" :key="apiToken.id"
            prepend-icon="mdi-key-variant"
          >
            <v-list-item-title>
              {{ apiToken.name }}
              <chip-expires class="ml-3" :value="apiToken.expire_date" />
            </v-list-item-title>
            <template #append>
              <btn-delete button-variant="icon" :delete="() => deleteApiToken(apiToken)" />
            </template>
          </v-list-item>
          <v-list-item>
            <s-dialog v-model="setupWizard.visible">
              <template #activator="{ props: dialogProps}">
                <s-btn
                  color="secondary"
                  @click="openSetupWizard"
                  v-bind="dialogProps"
                  prepend-icon="mdi-plus"
                  text="Add"
                />
              </template>
              <template #title>Setup API Token</template>
              <template #default>
                <template v-if="setupWizard.step === SetupWizardStep.INFO">
                  <v-card-text>
                    <s-text-field
                      v-model="setupWizard.form.name"
                      label="Name"
                      :error-messages="setupWizard.errors?.name"
                      class="mb-4"
                      autofocus
                      spellcheck="false"
                    />
                    <s-date-picker
                      v-model="setupWizard.form.expire_date"
                      label="Expire Date (optional)"
                      :error-messages="setupWizard.errors?.expire_date"
                    />
                  </v-card-text>
                  <v-card-actions>
                    <v-spacer />
                    <s-btn
                      @click="setupWizard.visible = false"
                      color="secondary"
                      variant="text"
                      text="Cancel"
                    />
                    <s-btn
                      @click="createApiToken"
                      color="primary"
                      :loading="setupWizard.actionInProgress"
                      text="Create"
                    />
                  </v-card-actions>
                </template>
                <template v-else-if="setupWizard.step === SetupWizardStep.TOKEN">
                  <v-card-text>
                    <p>
                      The API token <s-code>{{ setupWizard.newApiToken?.name }}</s-code> has been created successfully.<br>
                      Please copy the token and store it in a safe place.
                      You will not be able to see it again.
                    </p>
                    <pre class="token-preview"><s-code>Authorization: Bearer {{ setupWizard.newApiToken?.token }}</s-code></pre>
                  </v-card-text>
                  <v-card-actions>
                    <v-spacer />
                    <s-btn
                      @click="setupWizard.visible = false"
                      color="primary" text="Done"
                    />
                  </v-card-actions>
                </template>
              </template>
            </s-dialog>
          </v-list-item>
        </v-list>
      </v-card-text>
    </s-card>
  </div>
</template>

<script setup lang="ts">
const auth = useAuth();
const apiTokens = await useAsyncDataE<ApiToken[]>(async () => {
  try {
    return await $fetch<ApiToken[]>('/api/v1/pentestusers/self/apitokens/', { method: 'GET' });
  } catch (error: any) {
    if (error?.data?.code === 'reauth-required') {
      auth.redirectToReAuth();
      return [];
    } else {
      throw error;
    }
  }
});

enum SetupWizardStep {
  INFO = 'info',
  TOKEN = 'token',
}

const reauthDialogVisible = ref(false);
const setupWizard = ref({
  visible: false,
  step: SetupWizardStep.INFO,
  form: {
    name: '',
    expire_date: null as string|null,
  },
  errors: null as any|null,
  actionInProgress: false,
  newApiToken: null as ApiToken|null,
});

function openSetupWizard() {
  setupWizard.value = {
    visible: true,
    step: SetupWizardStep.INFO,
    form: {
      name: 'API Token',
      expire_date: null,
    },
    errors: null,
    actionInProgress: false,
    newApiToken: null
  };
}

async function createApiToken() {
  try {
    setupWizard.value.newApiToken = await $fetch<ApiToken>('/api/v1/pentestusers/self/apitokens/', {
      method: 'POST',
      body: setupWizard.value.form,
    });
    setupWizard.value.step = SetupWizardStep.TOKEN;
    apiTokens.value.push(setupWizard.value.newApiToken);
  } catch (error: any) {
    if (error?.data?.code === 'reauth-required') {
      setupWizard.value.visible = false;
      reauthDialogVisible.value = true;
    } else if (error?.data) {
      setupWizard.value.errors = error.data;
    } else {
      throw error;
    }
  }
}

async function deleteApiToken(apiToken: ApiToken) {
  try {
    await $fetch(`/api/v1/pentestusers/self/apitokens/${apiToken.id}/`, { method: 'DELETE' });
    apiTokens.value = apiTokens.value.filter(t => t.id !== apiToken.id);
  } catch (error) {
    requestErrorToast({ error });
  }
}
</script>

<style lang="scss" scoped>
.token-preview {
  white-space: pre-wrap;
  word-break: break-all;

  code {
    display: block;
  }
}
</style>
