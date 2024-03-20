2024.02.14 : 

## 1. Read raw data
Lire les raw data, sans conversion en gramme, pour vérifier pourquoi les lectures ont autant de données aberrantes. 
Scale : -6317.56			-16926.20			-17242.63
Offset : -583300.00			-706695.00			-4598767.00
Ça a bien converti


## 2. Les données aberrantes sont la cause du changement du plateau de offset. 
Nat pense que la raison pourquoi le offset monte super haut soudainement est parce que, quand on tare c'est quand on pèse un poids qui est plus petite qu'un seuil définit pour l'instant par le tier du poids d'une souris normale (20g/3). Par contre, il y a parfois des données abérrantes très élevés dans les négatifs ou les positifs qui sont lues. Si la donnée lue pendant le tare est très haute, positive, alors la loop de tare arrête et on repart à la lecture du poids. Si la donnée lue pendant le tare est très négative, bien le code reste dans le tare, parce que c'est tout de même une donnée plus faible que le tier du poids d'une souris normale. Donc, le offset/zéro monte, parce que le nouveau zéro est à -600 (mettons). Nat a changé le code pour que ça tare la valeur absolue des mesures. PI ÇA MARCHE. On a plus de offset de zéro qui change soudainement! 



## 3. J'ai fait 2 tests avec une souris : première avec le nouveau autotare en valeur absolue et le deuxième 20 min de données brutes. 

Ces tests montrent qu'il y a encore un shift dans le offset. Tant qu'à ça, on va enregistrer les données brutes et les analuyser par la suite en python. C'est plus safe. J'ai deux vidéos pour les deux tests.

​			Loadcell1 	Loadcell2 	Loadcell3

```
Offset : -582341.00			726332.00			4560257.00
Scale : -6422.02			16781.69			17258.59
```