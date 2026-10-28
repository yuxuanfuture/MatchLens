const words = {
  en:{headline:'GOAL!',confirmed:'GOAL CONFIRMED',title:'Goal confirmed! {team}',body:'{player} · {score}. The goal stands.',pending:'In the net — awaiting the decision',pendingBody:'{team} have the ball in the net. The score is unchanged pending the ruling.'},
  zh:{headline:'进球有效！',confirmed:'判罚已确认',title:'进球有效！{team}',body:'{player} · {score}。进球已获确认！',pending:'皮球入网，等待判罚',pendingBody:'{team} 将球送入网内，等待裁判判罚，比分暂不变更。'},
  fr:{headline:'BUT !',confirmed:'BUT CONFIRMÉ',title:'But confirmé ! {team}',body:'{player} · {score}. Le but est validé !',pending:'Au fond des filets — décision en attente',pendingBody:'{team} a envoyé le ballon au fond. Le score reste inchangé en attendant la décision.'},
  es:{headline:'¡GOL!',confirmed:'GOL CONFIRMADO',title:'¡Gol confirmado! {team}',body:'{player} · {score}. ¡El gol es válido!',pending:'En la red — decisión pendiente',pendingBody:'{team} envía el balón a la red. El marcador no cambia hasta la decisión.'},
  ar:{headline:'هدف!',confirmed:'تم تأكيد الهدف',title:'هدف مؤكد! {team}',body:'{player} · {score}. تم احتساب الهدف!',pending:'الكرة في الشباك — بانتظار القرار',pendingBody:'أودع {team} الكرة في الشباك. تبقى النتيجة دون تغيير حتى صدور القرار.'}
};

export function celebrationCopy(cue, language) {
  if (!cue) return null;
  const dictionary=words[language] ?? words.en;
  const score=cue.score ? `${cue.score.A} – ${cue.score.U}` : '';
  const values={team:cue.teamName,player:cue.playerName,score:`\u2066${score}\u2069`};
  const format=text=>text.replace(/\{(\w+)\}/g,(_,key)=>values[key]);
  return {headline:dictionary.headline,kicker:dictionary.confirmed,score,
    title:format(cue.kind==='confirmed'?dictionary.title:dictionary.pending),
    body:format(cue.kind==='confirmed'?dictionary.body:dictionary.pendingBody)};
}
