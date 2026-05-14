<template>
  <el-card class="tag-group-manager" shadow="hover" v-loading="isLoading">
    <template #header>
      <div class="card-header">
        <el-icon><PriceTag /></el-icon>
        <span>标签组管理</span>
      </div>
    </template>

    <div class="manager-content">
      <div class="group-selector">
        <el-select
          v-model="selectedGroupId"
          placeholder="选择标签组"
          class="group-select"
          @change="handleGroupChange"
        >
          <el-option
            v-for="group in sceneTagGroups"
            :key="group.id"
            :label="group.name"
            :value="group.id"
          >
            <span>{{ group.name }}</span>
            <el-tag v-if="group.is_default" type="success" size="small" class="default-mark">默认</el-tag>
          </el-option>
        </el-select>

        <el-button-group class="group-actions">
          <el-button type="primary" class="create-group-btn" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            新建
          </el-button>
          <el-button type="warning" class="edit-group-btn" @click="handleEditGroup" :disabled="!selectedGroupId">
            <el-icon><Edit /></el-icon>
            编辑
          </el-button>
          <el-button type="danger" class="delete-group-btn" @click="handleDeleteGroup" :disabled="!selectedGroupId">
            <el-icon><Delete /></el-icon>
            删除
          </el-button>
        </el-button-group>
      </div>

      <div v-if="selectedGroupId" class="tag-list">
        <div class="tag-list-header">
          <span>标签列表</span>
          <el-button type="primary" size="small" class="add-tag-btn" @click="showAddTagDialog = true">
            <el-icon><Plus /></el-icon>
            添加标签
          </el-button>
        </div>

        <el-table :data="tags" stripe style="width: 100%">
          <el-table-column prop="name" label="标签名称" width="150" />
          <el-table-column label="相似标签">
            <template #default="{ row }">
              <el-tag
                v-for="tag in row.similar_tags"
                :key="tag"
                size="small"
                class="similar-tag"
              >
                {{ tag }}
              </el-tag>
              <span v-if="!row.similar_tags || row.similar_tags.length === 0" class="no-similar">无</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button type="primary" size="small" class="edit-tag-btn" @click="handleEditTag(row)">
                编辑
              </el-button>
              <el-button type="danger" size="small" class="delete-tag-btn" @click="handleDeleteTag(row)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-else class="no-selection">
        <el-empty description="请选择一个标签组" />
      </div>
    </div>

    <el-dialog v-model="showCreateDialog" title="新建标签组" width="400px">
      <el-form :model="newGroupForm" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="newGroupForm.name" class="group-name-input" placeholder="输入标签组名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateGroup">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showEditDialog" title="编辑标签组" width="400px">
      <el-form :model="editGroupForm" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="editGroupForm.name" class="group-name-input" placeholder="输入标签组名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="handleUpdateGroup">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showAddTagDialog" title="添加标签" width="500px">
      <el-form :model="newTagForm" label-width="80px">
        <el-form-item label="标签名称">
          <el-input v-model="newTagForm.name" placeholder="输入标签名称" />
        </el-form-item>
        <el-form-item label="相似标签">
          <el-select v-model="newTagForm.similar_tags" multiple placeholder="选择相似标签" style="width: 100%">
            <el-option
              v-for="tag in availableSimilarTags"
              :key="tag"
              :label="tag"
              :value="tag"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddTagDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddTag">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showEditTagDialog" title="编辑标签" width="500px">
      <el-form :model="editTagForm" label-width="80px">
        <el-form-item label="标签名称">
          <el-input v-model="editTagForm.name" placeholder="输入标签名称" />
        </el-form-item>
        <el-form-item label="相似标签">
          <el-select v-model="editTagForm.similar_tags" multiple placeholder="选择相似标签" style="width: 100%">
            <el-option
              v-for="tag in availableSimilarTagsForEdit"
              :key="tag"
              :label="tag"
              :value="tag"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditTagDialog = false">取消</el-button>
        <el-button type="primary" @click="handleUpdateTag">确定</el-button>
      </template>
    </el-dialog>

    <el-alert v-if="error" :title="error" type="error" show-icon @close="clearError" />
  </el-card>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, PriceTag } from '@element-plus/icons-vue'
import { useTagStore } from '@/stores/tagStore'

const tagStore = useTagStore()

const selectedGroupId = ref(null)
const tags = ref([])
const isLoading = ref(false)
const error = ref(null)

const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const showAddTagDialog = ref(false)
const showEditTagDialog = ref(false)

const newGroupForm = ref({ name: '' })
const editGroupForm = ref({ name: '' })
const newTagForm = ref({ name: '', similar_tags: [] })
const editTagForm = ref({ id: null, name: '', similar_tags: [] })

const sceneTagGroups = computed(() => tagStore.sceneTagGroups)

const isDefaultGroup = computed(() => {
  const group = sceneTagGroups.value.find(g => g.id === selectedGroupId.value)
  return group?.is_default === 1
})

const availableSimilarTags = computed(() => {
  return tags.value
    .filter(t => t.name !== newTagForm.value.name)
    .map(t => t.name)
})

const availableSimilarTagsForEdit = computed(() => {
  return tags.value
    .filter(t => t.name !== editTagForm.value.name)
    .map(t => t.name)
})

const handleGroupChange = async (groupId) => {
  if (!groupId) {
    tags.value = []
    return
  }
  
  isLoading.value = true
  try {
    tags.value = await tagStore.fetchTagsByGroup(groupId)
  } catch (e) {
    error.value = e.message || '加载标签失败'
  } finally {
    isLoading.value = false
  }
}

const handleCreateGroup = async () => {
  if (!newGroupForm.value.name.trim()) {
    ElMessage.warning('请输入标签组名称')
    return
  }
  
  isLoading.value = true
  try {
    await tagStore.createTagGroup({ name: newGroupForm.value.name, type: 'scene' })
    await tagStore.fetchTagGroups()
    ElMessage.success('标签组创建成功')
    showCreateDialog.value = false
    newGroupForm.value.name = ''
  } catch (e) {
    error.value = e.message || '创建失败'
  } finally {
    isLoading.value = false
  }
}

const handleEditGroup = () => {
  const group = sceneTagGroups.value.find(g => g.id === selectedGroupId.value)
  if (group) {
    editGroupForm.value.name = group.name
    showEditDialog.value = true
  }
}

const handleUpdateGroup = async () => {
  if (!editGroupForm.value.name.trim()) {
    ElMessage.warning('请输入标签组名称')
    return
  }
  
  isLoading.value = true
  try {
    await tagStore.updateTagGroup(selectedGroupId.value, { name: editGroupForm.value.name })
    // 重新加载标签组列表，确保 store 数据同步
    await tagStore.fetchTagGroups()
    ElMessage.success('标签组更新成功')
    showEditDialog.value = false
  } catch (e) {
    error.value = e.message || '更新失败'
  } finally {
    isLoading.value = false
  }
}

const handleDeleteGroup = async () => {
  try {
    await ElMessageBox.confirm('确定要删除该标签组吗？删除后标签将一并删除。', '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    isLoading.value = true
    await tagStore.deleteTagGroup(selectedGroupId.value)
    await tagStore.fetchTagGroups()
    ElMessage.success('标签组删除成功')
    // 如果删除后还有默认组，自动选中
    const defaultGroup = tagStore.defaultTagGroup
    if (defaultGroup) {
      selectedGroupId.value = defaultGroup.id
      await handleGroupChange(defaultGroup.id)
    } else {
      selectedGroupId.value = null
      tags.value = []
    }
  } catch (e) {
    if (e !== 'cancel') {
      error.value = e.message || '删除失败'
    }
  } finally {
    isLoading.value = false
  }
}

const handleAddTag = async () => {
  if (!newTagForm.value.name.trim()) {
    ElMessage.warning('请输入标签名称')
    return
  }
  
  isLoading.value = true
  try {
    await tagStore.addTagToGroup(selectedGroupId.value, {
      name: newTagForm.value.name,
      similar_tags: newTagForm.value.similar_tags
    })
    ElMessage.success('标签添加成功')
    showAddTagDialog.value = false
    newTagForm.value = { name: '', similar_tags: [] }
    tags.value = await tagStore.fetchTagsByGroup(selectedGroupId.value)
  } catch (e) {
    error.value = e.message || '添加失败'
  } finally {
    isLoading.value = false
  }
}

const handleEditTag = (tag) => {
  editTagForm.value = {
    id: tag.id,
    name: tag.name,
    similar_tags: [...(tag.similar_tags || [])]
  }
  showEditTagDialog.value = true
}

const handleUpdateTag = async () => {
  if (!editTagForm.value.name.trim()) {
    ElMessage.warning('请输入标签名称')
    return
  }
  
  isLoading.value = true
  try {
    await tagStore.updateTag(editTagForm.value.id, {
      name: editTagForm.value.name,
      similar_tags: editTagForm.value.similar_tags
    })
    ElMessage.success('标签更新成功')
    showEditTagDialog.value = false
    tags.value = await tagStore.fetchTagsByGroup(selectedGroupId.value)
  } catch (e) {
    error.value = e.message || '更新失败'
  } finally {
    isLoading.value = false
  }
}

const handleDeleteTag = async (tag) => {
  try {
    await ElMessageBox.confirm(`确定要删除标签"${tag.name}"吗？`, '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    isLoading.value = true
    await tagStore.deleteTag(tag.id)
    ElMessage.success('标签删除成功')
    tags.value = await tagStore.fetchTagsByGroup(selectedGroupId.value)
  } catch (e) {
    if (e !== 'cancel') {
      error.value = e.message || '删除失败'
    }
  } finally {
    isLoading.value = false
  }
}

const clearError = () => {
  error.value = null
}

onMounted(async () => {
  await tagStore.fetchTagGroups()
  // 自动选中默认标签组
  const defaultGroup = tagStore.defaultTagGroup
  if (defaultGroup) {
    selectedGroupId.value = defaultGroup.id
    await handleGroupChange(defaultGroup.id)
  }
})
</script>

<style scoped>
.tag-group-manager {
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
}

.card-header .el-icon {
  font-size: 20px;
  color: #409EFF;
}

.manager-content {
  min-height: 200px;
}

.group-selector {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
  align-items: center;
}

.group-select {
  flex: 1;
  max-width: 300px;
}

.default-mark {
  margin-left: 8px;
}

.group-actions {
  flex-shrink: 0;
}

.tag-list {
  margin-top: 16px;
}

.tag-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  font-weight: 500;
}

.similar-tag {
  margin-right: 4px;
  margin-bottom: 4px;
}

.no-similar {
  color: #909399;
  font-size: 12px;
}

.no-selection {
  padding: 40px 0;
}

:deep(.el-table) {
  font-size: 14px;
}

:deep(.el-table th) {
  background-color: #f5f7fa;
}
</style>