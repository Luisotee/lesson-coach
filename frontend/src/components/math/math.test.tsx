import { render, screen, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { EquationLine, Fraction, MathExpr, Notebook, Pen, StepsNotebook } from '@/components/math'

describe('Fraction', () => {
  test('stacks the numerator over a bar and the denominator', () => {
    const { container } = render(<Fraction num="1" den="2" />)
    const frac = container.querySelector('[data-math="fraction"]')!
    expect(frac.children).toHaveLength(2)
    expect(frac.children[0]).toHaveTextContent('1')
    expect(frac.children[1]).toHaveTextContent('2')
    expect(frac.children[1]).toHaveClass('border-t-2')
  })
})

describe('MathExpr', () => {
  test('has spoken text, hides the drawing and stays left to right', () => {
    render(
      <div dir="rtl">
        <MathExpr expr="1/2 + 1/3" />
      </div>,
    )
    const math = screen.getByRole('math', { name: 'one half plus one third' })
    expect(math).toHaveAttribute('dir', 'ltr')
    expect(math.firstElementChild).toHaveAttribute('aria-hidden', 'true')
    expect(math.querySelectorAll('[data-math="fraction"]')).toHaveLength(2)
  })

  test('draws a minus sign, products and dropped fraction brackets', () => {
    const { container } = render(
      <>
        <MathExpr expr="5 - (-3)" />
        <MathExpr expr="(-2)*(-3)" />
        <MathExpr expr="(1+1)/(2+3)" />
        <MathExpr expr="3*x" />
      </>,
    )
    const [sub, mul, frac, juxt] = container.querySelectorAll('[role="math"]')
    expect(sub).toHaveTextContent('5−(−3)')
    expect(mul).toHaveTextContent('(−2)·(−3)')
    expect(frac).toHaveTextContent('1+12+3')
    expect(frac.textContent).not.toContain('(')
    expect(juxt).toHaveTextContent(/^3x$/)
  })

  test('shows text it cannot parse as written', () => {
    render(<MathExpr expr="sqrt(4)" />)
    expect(screen.getByRole('math', { name: 'sqrt(4)' })).toHaveTextContent('sqrt(4)')
  })
})

describe('Pen', () => {
  test.each([
    ['pencil', 'text-pencil'],
    ['ink', 'text-ink'],
    ['green', 'text-pen-green'],
  ] as const)('%s uses %s in the hand font', (variant, cls) => {
    render(<Pen variant={variant}>x</Pen>)
    expect(screen.getByText('x')).toHaveClass(cls, 'font-hand')
  })
})

describe('Notebook and EquationLine', () => {
  const steps = [
    { left: '3*x + 5', right: '20', op: '-5' },
    { left: '3*x', right: '15', op: '/3' },
    { left: 'x', right: '5', op: '' },
  ]

  test('lists each line with its spoken text, aligned in four shared columns', () => {
    render(
      <div dir="rtl">
        <StepsNotebook steps={steps} label="Worked example" />
      </div>,
    )
    const list = screen.getByRole('list', { name: 'Worked example' })
    expect(list.closest('[dir]')).toHaveAttribute('dir', 'ltr')
    const items = within(list).getAllByRole('listitem')
    expect(items).toHaveLength(3)
    for (const item of items) expect(item).toHaveClass('grid-cols-subgrid', 'col-span-full')
    expect(
      screen.getByRole('math', { name: '3 x plus 5 equals 20; subtract 5 from both sides' }),
    ).toBeInTheDocument()
    const cells = items[0].querySelectorAll('[role="math"] > span')
    expect(cells).toHaveLength(4)
    expect(cells[0]).toHaveTextContent('3x+5')
    expect(cells[1]).toHaveTextContent('=')
    expect(cells[2]).toHaveTextContent('20')
    expect(cells[3]).toHaveTextContent('|−5')
    expect(items[1].querySelectorAll('[role="math"] > span')[3]).toHaveTextContent('|÷3')
  })

  test('expression steps continue with =', () => {
    render(
      <StepsNotebook
        steps={[
          { left: '-5 - (-3)', right: '', op: '' },
          { left: '-5 + 3', right: '', op: '' },
        ]}
        label="Expression"
      />,
    )
    const [first, second] = screen.getAllByRole('math')
    expect(first).toHaveAccessibleName('negative 5 minus negative 3')
    expect(first.children[1]).toHaveTextContent('')
    expect(second).toHaveAccessibleName('equals negative 5 plus 3')
    expect(second.children[1]).toHaveTextContent('=')
  })

  test('write-on is motion-safe only and staggered', () => {
    render(
      <Notebook label="n" writeOn>
        <EquationLine left="x" right="5" index={2} />
      </Notebook>,
    )
    const line = screen.getByRole('math')
    expect(line).toHaveClass('motion-safe:animate-write')
    expect(line.style.animationDelay).toBe('1.6s')
  })

  test('no write-on unless asked', () => {
    render(
      <Notebook label="n">
        <EquationLine left="x" right="5" />
      </Notebook>,
    )
    expect(screen.getByRole('math').className).not.toContain('animate-write')
  })
})
