interface StepsIndicatorProps {
  current: number
}

const STEPS = ['Scrapear', 'Analizar', 'Configurar', 'Ejecutar']

export function StepsIndicator({ current }: StepsIndicatorProps) {
  return (
    <div className="steps">
      {STEPS.map((label, i) => {
        const n = i + 1
        const cls = n < current ? 'step done' : n === current ? 'step active' : 'step'
        return (
          <div key={n} className={cls}>
            <span className="num">{n}</span>
            {label}
          </div>
        )
      })}
    </div>
  )
}
