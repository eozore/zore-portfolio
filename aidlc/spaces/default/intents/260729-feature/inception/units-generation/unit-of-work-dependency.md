# Unit of Work Dependencies

U-1 → independente (pode ser feito primeiro)
U-2 → independente
U-3 → independente
U-4 → independente (mas logicamente após U-3 para logs limpos)
U-5 → independente de U-1..U-4, mas deve ser estável antes de U-6
U-6 → depende de U-5 estar validado (BUG2 muda contratos Pub/Sub — deploy coordenado final)

Ordem recomendada: U-1 → U-2 → U-3 → U-4 → U-5 → U-6
