import math, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def wilson(k,n,z=1.96):
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return p, c-h, c+h

sets=[
 ("Held-out + fresh", "80 pairs, 74 decided", {"P2g":{"acc":(63,74),"rec":(20,28),"fr":(3,46)},
                                             "JSON":{"acc":(48,74),"rec":(7,28),"fr":(5,46)},
                                             "D":{"acc":(67,74),"rec":(21,28),"fr":(0,46)}}),
 ("Extension", "120 pairs, 115 decided", {"P2g":{"acc":(103,115),"rec":(33,35),"fr":(10,80)}}),
 ("Diversity (3 runtimes)", "170 pairs, 164 decided", {"P2g":{"acc":(141,164),"rec":(38,47),"fr":(14,117)}}),
 ("Fresh repositories", "120 pairs, 94 decided", {"P2g":{"acc":(87,94),"rec":(31,35),"fr":(3,59)},
                                                "D":{"acc":(85,94),"rec":(29,35),"fr":(3,59)}}),
]
arms={"P2g":("SkillC: Controlled English bound to the runtime (P2g)","#2a78d6","o"),
      "JSON":("SkillC: original JSON compaction","#eb6834","s"),
      "D":("Direct model verdict, no logical block (baseline)","#1baf7a","^")}
metrics=[("acc","Decided accuracy",(0,100)),("rec","Impossible tasks caught",(0,100)),("fr","Achievable tasks blocked",(0,40))]
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":7,"axes.edgecolor":"#c9c8c3","axes.labelcolor":"#52514e",
                     "xtick.color":"#52514e","ytick.color":"#0b0b0b"})
fig,axes=plt.subplots(1,3,figsize=(6.5,1.95),sharey=True,gridspec_kw={"width_ratios":[1,1,0.8]})
order=["JSON","P2g","D"]; off={"JSON":0.26,"P2g":0.0,"D":-0.26}
ys=list(range(len(sets)))[::-1]
for ax,(m,title,xl) in zip(axes,metrics):
    for y,(lab,sub,data) in zip(ys,sets):
        for arm in order:
            if arm not in data: continue
            k,n=data[arm][m]; p,lo,hi=wilson(k,n); col=arms[arm][1]; yy=y+off[arm]
            ax.plot([lo*100,hi*100],[yy,yy],color=col,lw=1.3,solid_capstyle='round',alpha=0.5,zorder=2)
            ax.plot(p*100,yy,marker=arms[arm][2],ms=4.6,color=col,mec='white',mew=0.7,zorder=3,ls='none')
            if hi*100 > xl[1]-14: ax.annotate(f"{k}/{n}",(lo*100,yy),xytext=(-3,0),textcoords='offset points',va='center',ha='right',fontsize=5.6,color="#52514e",zorder=4)
            else: ax.annotate(f"{k}/{n}",(hi*100,yy),xytext=(3,0),textcoords='offset points',va='center',ha='left',fontsize=5.6,color="#52514e",zorder=4)
    ax.set_title(title,fontsize=7.2,color="#0b0b0b",pad=4,loc='left')
    ax.set_xlim(*xl); ticks=list(range(xl[0],xl[1]+1,25 if xl[1]==100 else 10))
    ax.set_xticks(ticks); ax.set_xticklabels([f"{t}%" if t==ticks[-1] else str(t) for t in ticks])
    ax.grid(axis='x',color="#ecebe7",lw=0.7,zorder=0); ax.set_axisbelow(True)
    for s in ("top","right","left"): ax.spines[s].set_visible(False)
    ax.tick_params(axis='y',length=0); ax.tick_params(axis='x',length=2,labelsize=6.2,pad=1.5)
    ax.set_ylim(-0.6,len(sets)-0.4)
axes[0].set_yticks(ys); axes[0].set_yticklabels([f"{s[0]}\n{s[1]}" for s in sets],fontsize=6.4,linespacing=1.25)
handles=[plt.Line2D([],[],marker=arms[a][2],color=arms[a][1],ls='none',ms=4.6,label=arms[a][0]) for a in ("P2g","JSON","D")]
fig.legend(handles=handles,loc='lower center',ncol=3,frameon=False,fontsize=6,bbox_to_anchor=(0.5,0.0),handletextpad=0.3,columnspacing=1.0)
fig.subplots_adjust(left=0.185,right=0.99,top=0.9,bottom=0.27,wspace=0.14)
fig.savefig('/tmp/claude-0/-home-user-skill-achievability-compiler/5af52808-1e99-510f-97e2-1dc92a0594bf/scratchpad/fig/realskills.png',dpi=300,facecolor='white')
print("ok")
