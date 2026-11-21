import { getStudyAdvice } from '../../services/api'
import type { StudyAdviceData } from '../../services/api'
import { useState, useEffect, useCallback } from 'react'
import { View, Text, Textarea, Image } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { 
  generateQuizAsync,      // ← 创建异步生成任务
  pollQuizTask,           // ← 轮询任务状态
  getCachedUser,          // ← 获取缓存的用户信息
  getQuizHistory,         // ← 获取闯关历史
  waitForLogin            // ← 等待登录完成
} from '../../services/api'
import type { UserBrief, QuizHistoryItem } from '../../services/api'
import './index.scss'

export default function IndexPage() {
  const [adviceLoading, setAdviceLoading] = useState(false)

  const [adviceData, setAdviceData] =useState<StudyAdviceData | null>(null)
  const [inputValue, setInputValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingText, setLoadingText] = useState('生成中...')
  const [generateImages, setGenerateImages] = useState(false)
  const [user, setUser] = useState<UserBrief | null>(null)
  const [historyItems, setHistoryItems] = useState<QuizHistoryItem[]>([])

  const loadData = useCallback(async () => {
    await waitForLogin()
    const cached = getCachedUser()
    if (cached) setUser(cached)

    getQuizHistory(1, 4)
      .then((res) => setHistoryItems(res.items))
      .catch(() => {})
  }, [])

  useEffect(() => { loadData() }, [loadData])

  // 每次页面显示时刷新（从其他页面返回后）
  useDidShow(() => {
    const cached = getCachedUser()
    if (cached) setUser(cached)
    // 刷新闯关历史（从报告页返回或新完成闯关后）
    getQuizHistory(1, 4)
      .then((res) => setHistoryItems(res.items))
      .catch(() => {})
  })

  const handleGenerate = async () => {
    const trimmed = inputValue.trim()
    if (!trimmed) {
      Taro.showToast({ title: '请输入学习内容', icon: 'none' })
      return
    }

    setLoading(true)
    setLoadingText('正在创建任务...')
    try {
      // 1. 创建异步任务（秒级返回）
      const { task_id } = await generateQuizAsync(trimmed, 5, undefined, generateImages)

      setLoadingText('AI 正在联网搜索并生成题目...')

      // 2. 轮询等待任务完成
      const quizData = await pollQuizTask(task_id, (status) => {
        if (status === 'running') setLoadingText('AI 正在生成题目...')
      })

      // 若配图有提示（如未登录/额度不足），友好告知，不阻断闯关
      if (quizData.image_notice) {
        Taro.showToast({ title: quizData.image_notice, icon: 'none', duration: 3000 })
      }

      // 3. 跳转闯关页
      Taro.navigateTo({
        url: `/pages/quiz/index?quizData=${encodeURIComponent(JSON.stringify(quizData))}`,
      })
    } catch (err: any) {
      Taro.showToast({ title: err.message || '生成失败，请稍后重试', icon: 'none' })
    } finally {
      setLoading(false)
      setLoadingText('生成中...')
    }
  }

  const handleStudyAdvice = async () => {
  if (adviceLoading) return

  const text = inputValue.trim()

  if (!text) {
    Taro.showToast({
      title: '请输入学习需求',
      icon: 'none',
    })
    return
  }

  setAdviceLoading(true)
  setAdviceData(null)

  try {
    const data = await getStudyAdvice(text)
    setAdviceData(data)
  } catch (error: unknown) {
    Taro.showToast({
      title: error instanceof Error
        ? error.message
        : '获取学习建议失败',
      icon: 'none',
    })
  } finally {
    setAdviceLoading(false)
  }
}

  return (
    <View className='index-page'>
      {/* 顶部工具栏 */}
      <View className='toolbar'>
        <View className='hello-user'>
          {user?.avatar_url ? (
            <Image className='hello-avatar-img' src={user.avatar_url} mode='aspectFill' />
          ) : (
            <View className='hello-avatar'>
              <Text>{user?.nickname?.[0] || '鱼'}</Text>
            </View>
          )}
          <Text className='hello-name'>你好，{user?.nickname || '同学'}</Text>
        </View>
        <View className='coin-badge'>
          <Text className='coin-text'>{user?.total_xp ?? 0}</Text>
          <Text className='coin-icon'>⭐</Text>
        </View>
      </View>

      {/* 标题 */}
      <Text className='page-title'>今天想闯哪一关？</Text>

      {/* 输入区域 */}
      <View className='quick-input'>
        <View className='input-head'>
          <View className='input-label'>输入你想学的内容</View>
          <View className='mini-mascot'>🐟</View>
        </View>
        <Textarea
          className='input-area'
          placeholder={'例如：RAG 和传统搜索有什么区别？\n我想搞懂向量数据库是怎么配合工作的。\n最好通过闯关题帮我记住重点。'}
          value={inputValue}
          onInput={(e) => setInputValue(e.detail.value)}
          maxlength={500}
          autoHeight
        />
        <View
          className={`image-toggle-row ${generateImages ? 'is-active' : ''}`}
          onClick={() => setGenerateImages((prev) => !prev)}
        >
          <View className='image-toggle-info'>
            <Text className='image-toggle-icon'>🖼️</Text>
            <Text className='image-toggle-label'>为题目生成配图</Text>
          </View>
          <View className={`toggle-pill ${generateImages ? 'is-on' : ''}`}>
            <View className='toggle-knob' />
          </View>
        </View>
        <View className='input-actions'>
          <View
            className={`btn-primary generate-btn ${loading ? 'is-loading' : ''}`}
            onClick={!loading ? handleGenerate : undefined}
          >
            {loading ? (
              <Text>{loadingText}</Text>
            ) : (
              <>
                <Text className='btn-arrow'>→</Text>
                <Text>开始生成题目</Text>
              </>
            )}
          </View>
        </View>
      </View>

      {/* 已完成关卡 */}
      {historyItems.length > 0 && (
        <View className='cards-grid'>
          {historyItems.map((item) => (
            <View
              key={item.quiz_id}
              className='quiz-card'
              onClick={() => {
                Taro.navigateTo({
                  url: `/pages/report/index?quizId=${item.quiz_id}`,
                })
              }}
            >
              <View className='quiz-dot'>✓</View>
              <View className='quiz-body'>
                <Text className='quiz-name'>{item.title}</Text>
                <Text className='quiz-meta'>正确率：{Math.round(item.accuracy)}% · {item.question_count} 题</Text>
              </View>
            </View>
          ))}
        </View>
      )}

      {/* 学习小贴士 */}
      <Text className='section-title'>💡 学习小贴士</Text>
      <View className='tip-list'>
        <View className='tip-item'>
          <Text className='tip-icon'>🎯</Text>
          <Text className='tip-text'>每天坚持闯关一次，知识积累看得见</Text>
        </View>
        <View className='tip-item'>
          <Text className='tip-icon'>📝</Text>
          <Text className='tip-text'>完成闯关后查看报告，重点复习薄弱知识点</Text>
        </View>
        <View className='tip-item'>
          <Text className='tip-icon'>⭐</Text>
          <Text className='tip-text'>答对越多，经验值涨得越快哦</Text>
        </View>
      </View>

    <View
  className='btn-primary'
  style={{ marginTop: '24px' }}
  onClick={adviceLoading ? undefined : handleStudyAdvice}
>
  <Text>
    {adviceLoading ? '正在安排学习计划...' : '获取学习建议'}
  </Text>
</View>

{adviceData && (
  <View
    style={{
      marginTop: '24px',
      padding: '24px',
      borderRadius: '16px',
      background: '#fff7ed',
    }}
  >
    {adviceData.clock && (
      <View style={{ marginBottom: '16px' }}>
        <Text style={{ display: 'block' }}>
          当前时间：
          {adviceData.clock.current_time.replace('T', ' ')}
        </Text>

        <Text style={{ display: 'block' }}>
          时区：{adviceData.clock.timezone}
        </Text>

        <Text style={{ display: 'block' }}>
          建议学习 {adviceData.clock.suggested_study_minutes} 分钟，
          休息 {adviceData.clock.suggested_break_minutes} 分钟
        </Text>
      </View>
    )}

    <Text>{adviceData.advice}</Text>
  </View>
)}
</View>
  )
}
