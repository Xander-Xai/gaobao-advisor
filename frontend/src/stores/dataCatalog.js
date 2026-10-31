import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import { dataAPI } from '../api/client'

const PAGE_SIZE = 6

function messageOf(error) {
  return error?.message || '请求失败，请稍后重试'
}

export const useDataCatalogStore = defineStore('dataCatalog', () => {
  const overview = ref(null)
  const overviewLoading = ref(false)
  const overviewError = ref('')

  const filterOptions = ref(null)
  const filters = reactive({ q: '', province: '', level: '', schoolType: '' })

  const schools = ref([])
  const total = ref(0)
  const nextCursor = ref(null)
  const hasMore = ref(false)
  const schoolsLoading = ref(false)
  const schoolsError = ref('')

  const selectedSchool = ref(null)
  const selectedSchoolId = ref(null)
  const detailLoading = ref(false)
  const detailError = ref('')

  const trend = ref(null)
  const trendLoading = ref(false)
  const trendError = ref('')
  const selectedSubject = ref('')
  const trendMajor = ref('')

  const visibleSeries = computed(() => {
    if (!trend.value?.series?.length) return []
    if (!selectedSubject.value) return trend.value.series
    return trend.value.series.filter(series => series.subject_type === selectedSubject.value)
  })

  const hasActiveFilters = computed(
    () => Boolean(filters.q || filters.province || filters.level || filters.schoolType),
  )

  async function loadOverview() {
    overviewLoading.value = true
    overviewError.value = ''
    const { data, error } = await dataAPI.overview()
    if (error) overviewError.value = messageOf(error)
    else overview.value = data
    overviewLoading.value = false
  }

  async function loadFilters() {
    const { data, error } = await dataAPI.filters()
    if (error) {
      schoolsError.value = messageOf(error)
      return
    }
    filterOptions.value = data
  }

  async function loadSchools({ append = false } = {}) {
    if (schoolsLoading.value) return
    schoolsLoading.value = true
    schoolsError.value = ''
    const cursor = append ? nextCursor.value : null
    const { data, error } = await dataAPI.searchSchools({
      q: filters.q.trim() || undefined,
      province: filters.province || undefined,
      level: filters.level || undefined,
      schoolType: filters.schoolType || undefined,
      limit: PAGE_SIZE,
      cursor,
    })
    if (error) {
      schoolsError.value = messageOf(error)
      if (!append) {
        schools.value = []
        total.value = 0
        nextCursor.value = null
        hasMore.value = false
      }
    } else {
      const items = data.items || []
      schools.value = append ? [...schools.value, ...items] : items
      total.value = Number(data.total ?? schools.value.length)
      nextCursor.value = data.next_cursor ?? null
      hasMore.value = Boolean(data.has_more)
    }
    schoolsLoading.value = false
  }

  function applyFilters() {
    selectedSchool.value = null
    return loadSchools()
  }

  function resetFilters() {
    filters.q = ''
    filters.province = ''
    filters.level = ''
    filters.schoolType = ''
    return applyFilters()
  }

  async function selectSchool(id) {
    detailLoading.value = true
    detailError.value = ''
    selectedSchoolId.value = id
    selectedSchool.value = null
    trend.value = null
    trendError.value = ''
    trendMajor.value = ''
    selectedSubject.value = ''
    const { data, error } = await dataAPI.schoolDetail(id)
    if (error) detailError.value = messageOf(error)
    else selectedSchool.value = data
    detailLoading.value = false
    if (data) await loadTrend({ schoolName: data.name, province: data.province })
  }

  async function loadTrend({ schoolName, province } = {}) {
    const school = selectedSchool.value
    if (!school) return
    const targetName = schoolName || school.name
    const targetProvince = province || school.province
    trendLoading.value = true
    trendError.value = ''
    const { data, error } = await dataAPI.trend({
      schoolName: targetName,
      province: targetProvince,
      major: trendMajor.value || undefined,
      years: 3,
    })
    if (error) {
      trendError.value = messageOf(error)
      trend.value = null
    } else {
      trend.value = data
      const subjects = (data.series || []).map(series => series.subject_type)
      if (!subjects.includes(selectedSubject.value)) selectedSubject.value = subjects[0] || ''
    }
    trendLoading.value = false
  }

  function closeSchool() {
    selectedSchool.value = null
    selectedSchoolId.value = null
    detailError.value = ''
    trend.value = null
    trendError.value = ''
    selectedSubject.value = ''
    trendMajor.value = ''
  }

  return {
    overview,
    overviewLoading,
    overviewError,
    filterOptions,
    filters,
    schools,
    total,
    nextCursor,
    hasMore,
    schoolsLoading,
    schoolsError,
    selectedSchool,
    selectedSchoolId,
    detailLoading,
    detailError,
    trend,
    trendLoading,
    trendError,
    selectedSubject,
    trendMajor,
    visibleSeries,
    hasActiveFilters,
    loadOverview,
    loadFilters,
    loadSchools,
    applyFilters,
    resetFilters,
    selectSchool,
    loadTrend,
    closeSchool,
  }
})
