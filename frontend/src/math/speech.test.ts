import { afterAll, beforeAll, describe, expect, test } from 'vitest'
import i18n from '@/i18n'
import { speakLine, speakText } from '@/math/speech'

describe('spoken text in English', () => {
  const t = i18n.getFixedT('en')
  test.each([
    ['1/2 + 1/3', 'one half plus one third'],
    ['2/3', '2 thirds'],
    ['3/4 - 1/4', '3 quarters minus one quarter'],
    ['7/12', '7 over 12'],
    ['x/2', 'x over 2'],
    ['(1+1)/(2+3)', 'the fraction with numerator 1 plus 1 and denominator 2 plus 3'],
    ['5 - (-3)', '5 minus negative 3'],
    ['(-2)*(-3)', 'negative 2 times negative 3'],
    ['-5 + 3', 'negative 5 plus 3'],
    ['3*x + 5 = 20', '3 x plus 5 equals 20'],
    ['2*(x + 3)', '2 times open bracket, x plus 3, close bracket'],
    ['x**2', 'x squared'],
    ['x^3', 'x cubed'],
    ['2^5', '2 to the power of 5'],
    ['3*5', '3 times 5'],
  ])('%s → %s', (src, spoken) => {
    expect(speakText(src, t)).toBe(spoken)
  })

  test.each([
    ['(-3)**2 = 9', 'open bracket, negative 3, close bracket squared equals 9'],
    ['-3**2 = -9', 'negative 3 squared equals negative 9'],
    ['(-x)**2', 'open bracket, negative x, close bracket squared'],
    ['-x**2', 'negative x squared'],
    ['2**(x + 1)', '2 to the power of x plus 1, end of exponent'],
    ['2**x + 1', '2 to the power of x plus 1'],
    ['2^3^2', '2 to the power of 3 squared, end of exponent'],
    ['(2^3)^2', 'open bracket, 2 cubed, close bracket squared'],
    ['(x + 1)**2', 'open bracket, x plus 1, close bracket squared'],
    ['(x)**2', 'x squared'],
    ['x**(2)', 'x squared'],
  ])('powers are unambiguous: %s', (src, spoken) => {
    expect(speakText(src, t)).toBe(spoken)
  })

  test('unparseable text is read as written', () => {
    expect(speakText('sqrt(4)', t)).toBe('sqrt(4)')
  })

  test('lines with margin operations', () => {
    expect(speakLine({ left: '3*x + 5', right: '20', op: '-5' }, t)).toBe(
      '3 x plus 5 equals 20; subtract 5 from both sides',
    )
    expect(speakLine({ left: '3*x', right: '15', op: '/3' }, t)).toBe(
      '3 x equals 15; divide both sides by 3',
    )
    expect(speakLine({ left: 'x/2', right: '4', op: '*2' }, t)).toBe(
      'x over 2 equals 4; multiply both sides by 2',
    )
    expect(speakLine({ left: 'x - 4', right: '1', op: '+4' }, t)).toBe(
      'x minus 4 equals 1; add 4 to both sides',
    )
  })

  test('expression lines', () => {
    expect(speakLine({ left: '-5 - (-3)' }, t)).toBe('negative 5 minus negative 3')
    expect(speakLine({ left: '-2', continued: true }, t)).toBe('equals negative 2')
  })
})

describe('spoken text in Arabic', () => {
  beforeAll(() => i18n.loadLanguages('ar'))
  afterAll(() => i18n.changeLanguage('en'))

  test('uses the Arabic locale', () => {
    const t = i18n.getFixedT('ar')
    expect(speakText('1/2 + 1/3', t)).toBe('1 على 2 زائد 1 على 3')
    expect(speakText('2**(x + 1)', t)).toBe('2 أس x زائد 1، نهاية الأس')
    expect(speakLine({ left: '3*x + 5', right: '20', op: '-5' }, t)).toBe(
      '3 x زائد 5 يساوي 20؛ اطرح 5 من الطرفين',
    )
  })
})
