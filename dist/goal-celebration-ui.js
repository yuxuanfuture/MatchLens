import { celebrationCopy } from './goal-celebration-copy.js';

const clamp=value=>Math.max(0,Math.min(1,value));

export class GoalCelebrationUI {
  constructor() {
    const $=id=>document.getElementById(id);
    this.banner=$('goal-celebration');this.card=document.querySelector('.commentary-module');
    this.score=$('score');this.status=$('review-status');
    this.title=$('commentary-title');this.body=$('commentary-body');
    this.headline=$('goal-headline');this.kicker=$('goal-kicker');this.player=$('goal-player');this.goalScore=$('goal-score');
  }

  updateContent(cue, language) {
    const copy=celebrationCopy(cue,language);
    if (!copy) return;
    this.title.textContent=copy.title;this.body.textContent=copy.body;
    this.headline.textContent=copy.headline;this.kicker.textContent=copy.kicker;
    this.player.textContent=cue.playerName;this.goalScore.textContent=copy.score;
  }

  render(cue, {reduced, time, reviewPhase}) {
    const confirmed=cue?.kind==='confirmed', age=cue?.age ?? 0;
    this.card.toggleAttribute('data-celebrating',confirmed);
    this.banner.hidden=!confirmed || age>=3.2;
    this.banner.dataset.team=cue?.team ?? '';
    const fade=1-clamp((age-2.2)/1), strength=confirmed?1-clamp((age-4)/1):0;
    const pop=reduced?0:Math.sin(clamp(age/.65)*Math.PI);
    this.banner.style.setProperty('--goal-opacity',String(reduced?1:clamp(age/.12)*fade));
    this.banner.style.setProperty('--goal-scale',String(1+pop*.12));
    this.card.style.setProperty('--goal-lift',`${reduced?0:-pop*10*strength}px`);
    this.card.style.setProperty('--goal-glow',String(reduced?0:strength));
    this.score.style.transform=confirmed&&!reduced?`scale(${1+pop*.22})`:'';
    const reviewing=['checking','review_requested','reviewing','awaiting_decision'].includes(reviewPhase);
    this.status.style.setProperty('--review-glow',String(reviewing&&!reduced ? .5+.5*Math.sin(time*1.8) : 0));
  }
}
