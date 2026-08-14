# Risk and Sequencing Rationale

BUG2 é o último pois muda AvatarCompletedMsg (breaking change em 3 serviços). Deploy deve ser coordenado.
BUG1 antes de BUG2 pois os slides visuais são o conteúdo que o VideoEditor vai combinar com os vídeos por segmento.
BUG3-5 primeiro pois são simples e independentes — validam que o fluxo de codegen funciona.
