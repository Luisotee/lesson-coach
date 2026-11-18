import { expect, test } from 'vitest'
import i18n from '@/i18n'
import { speak } from '@/math/speech'
import { substituteAnswer } from '@/math/substitute'

const t = i18n.getFixedT('en')
const said = (eq: string, ans: string) => {
  const node = substituteAnswer(eq, ans)
  return node && speak(node, t)
}

test.each([
  ['3*x + 5 = 20', '5', '3 times 5 plus 5 equals 20'],
  ['3*x + 5 = 20', 'x = 5', '3 times 5 plus 5 equals 20'],
  ['2*x + 6 = 10', '2 = x', '2 times 2 plus 6 equals 10'],
  ['x + 3 = 1', '-2', 'negative 2 plus 3 equals 1'],
  ['2*x = 1', '1/2', '2 times one half equals 1'],
])('%s with %s', (eq, ans, spoken) => {
  expect(said(eq, ans)).toBe(spoken)
})

test.each([
  ['3*x + 5', '5'],
  ['x + y = 3', '1'],
  ['2*x = 4', 'y = 2'],
  ['2*x = 4', 'sqrt(4)'],
])('nothing to check for %s with %s', (eq, ans) => {
  expect(substituteAnswer(eq, ans)).toBeNull()
})
