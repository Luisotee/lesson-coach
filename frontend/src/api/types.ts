/**
 * The API's JSON shapes (T6 contract, `backend/app/api/models.py`; Pack from
 * `backend/app/content/schema.py`). Math is always plain sympy text; prose may carry inline
 * math in backticks.
 */
import type { TopicId } from '@/content/topics'
import type { Step } from '@/math/types'

export type ProblemKind = 'evaluate' | 'simplify' | 'solve'

export interface Problem {
  kind: ProblemKind
  expr: string
}

export interface StepExplanations {
  why: string
  another_way: string
  /** A caption-length sentence; the picture itself is drawn from the step's math. */
  visual: string
}

export interface ExplainedStep extends Step {
  explanations?: StepExplanations | null
}

export interface WorkedExample {
  /** Instruction only ("Solve:"); always shown beside `problem.expr`. */
  prompt?: string
  problem: Problem
  steps: ExplainedStep[]
  answer: string
  ai_generated?: string[]
}

export interface WhatToSay {
  probe: string
  nudge: string
  tell: string
}

export interface Misconception {
  id: string
  belief: string
  rule_sympy?: string | null
  example_problem: Problem
  example_wrong_answer: string
  why_it_feels_right: string
  what_to_say: WhatToSay
  check_question: { problem: Problem; prompt: string; answer: string }
  source_quote: string
  ai_generated?: string[]
}

export type HintRung = 'goal' | 'information' | 'computation' | 'answer'

export interface PracticeItem {
  id: string
  problem: Problem
  /** Instruction only ("Solve:"); always shown beside `problem.expr`. */
  prompt: string
  hints: { rung: HintRung; text: string }[]
  answer: string
  source: {
    repo: string
    commit: string
    path: string
    url: string
    oer: string
    license: string
    changes: string
  }
  license: string
  ai_generated?: string[]
}

export interface AkeliusLesson {
  url: string
  title: string
  grade: number
}

export interface Pack {
  topic: TopicId
  lang: string
  title: string
  /** Being added by T5; absent until then. */
  grades?: number[]
  summary?: string | null
  /** Null when generation was dropped by verification: shown as unavailable. */
  idea: string | null
  why_it_works: string | null
  /** Paths of generated fields that failed verification and were dropped. */
  unavailable?: string[]
  prerequisites: TopicId[]
  worked_examples: WorkedExample[]
  misconceptions: Misconception[]
  questions: { question: string; answer: string }[]
  outline: { minutes: number; title: string; activity: string }[]
  akelius_lessons: AkeliusLesson[]
  practice: PracticeItem[]
  machine_translated: boolean
}

export interface TopicSummary {
  id: TopicId
  title: string
  lang: string
  langs: string[]
  machine_translated: boolean
  prerequisites: TopicId[]
  /** Empty / null until T5 fills them. */
  grades: number[]
  summary: string | null
}

/** Math as the teacher gave it: plain text, or LaTeX from MathLive. */
export type MathIn = { text: string } | { latex: string }

export type ProblemIn = MathIn & { kind?: ProblemKind }

export type LineIn = { left: string; right?: string; op?: string } | ({ op?: string } & MathIn)

export interface MistakeRequest {
  problem: ProblemIn
  answer: MathIn
  working?: LineIn[]
  topic?: TopicId
  lang: string
}

export type MistakeStatus =
  'correct' | 'not_simplified' | 'diagnosed' | 'slip' | 'unclear' | 'out_of_scope'

export type AbstainReason =
  'problem_unreadable' | 'answer_unreadable' | 'unsupported' | 'timeout' | 'ai_unavailable'

export type Verdict = 'correct' | 'equivalent_not_simplified' | 'wrong'

/** The first line (0-based, in the order sent) that doesn't follow from the one before. */
export interface FirstBadLine {
  index: number
  reason: 'unparsable' | 'false_equality' | 'not_equivalent' | 'unsupported'
}

export interface Diagnosis {
  source: 'rule' | 'ai'
  rule_checked: boolean
  /** ≤ 2 cards. `id: "other"` has null `belief` and `why_it_feels_right`. */
  misconceptions: { id: string; belief: string | null; why_it_feels_right: string | null }[]
  explanation: string
  margin_note: string | null
  what_to_say: WhatToSay
  try_next: { problem: Problem; prompt: string } | null
  /** Language of `explanation`, `margin_note` and `what_to_say`. */
  lang: string
  /** Language of `misconceptions` and `try_next` (the pack served); null on the AI path. */
  cards_lang: string | null
  machine_translated: boolean
}

export interface MistakeResult {
  status: MistakeStatus
  reason: AbstainReason | null
  problem: Problem | null
  student_answer: string | null
  correct_answer: string | null
  verdict: Verdict | null
  worked_solution: Step[]
  first_bad_line: FirstBadLine | null
  diagnosis: Diagnosis | null
  /** The student's working as parsed, in the order sent; an unreadable line has its raw
   * text in `left`, so `first_bad_line.index` lines up. */
  working?: Step[]
}

export interface CheckWorkingRequest {
  problem?: ProblemIn
  lines: LineIn[]
}

export interface CheckWorkingResult {
  status: 'all_follow' | 'line_doesnt_follow' | 'unclear' | 'out_of_scope'
  reason: AbstainReason | null
  first_bad_line: FirstBadLine | null
  /** The verdict on the last line, set only when every line follows and a problem was given. */
  final: Verdict | null
  /** The lines as parsed, in the order sent (requested from T6). */
  lines?: Step[]
}
