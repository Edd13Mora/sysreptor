<template>
  <v-container class="pt-0">
    <v-form ref="form">
      <edit-toolbar v-bind="toolbarAttrs" :form="$refs.form">
        <template #context-menu>
          <btn-copy
            v-if="auth.hasScope('designer')"
            :copy="performCopy"
            tooltip-text="Duplicate Design"
          />
          <btn-export
            :export-url="`/api/v1/projecttypes/${projectType.id}/export/`"
            :name="'design-' + projectType.name"
          />
        </template>
      </edit-toolbar>

      <p v-if="projectType.copy_of" class="mt-4">
        This design is a copy
        <s-btn
          :to="`/designs/${projectType.copy_of}/`"
          variant="text"
          size="small"
          prepend-icon="mdi-chevron-right-circle-outline"
          text="show original"
          class="ml-1 mr-1"
        />
      </p>
      <s-text-field
        v-model="projectType.name"
        label="Name"
        :disabled="readonly"
        class="mt-4"
        spellcheck="false"
      />
      <s-language-selection
        v-model="projectType.language"
        :disabled="readonly"
        class="mt-4"
      />
    </v-form>
  </v-container>
</template>

<script setup lang="ts">
import { useProjectTypeLockEditOptions } from "~/composables/lockedit";

const auth = useAuth();
const projectTypeStore = useProjectTypeStore();

const { projectType, toolbarAttrs, readonly } = useProjectTypeLockEdit(await useProjectTypeLockEditOptions({
  save: true,
  delete: true,
  saveFields: ['name', 'language'],
}));

async function performCopy() {
  const obj = await projectTypeStore.copy({
    id: projectType.value.id,
    scope: ProjectTypeScope.GLOBAL,
  });
  await navigateTo(`/designs/${obj.id}/pdfdesigner/`);
}
</script>
