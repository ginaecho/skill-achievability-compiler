
(** val negb : bool -> bool **)

let negb = function
| true -> false
| false -> true

(** val fst : ('a1 * 'a2) -> 'a1 **)

let fst = function
| (x, _) -> x

(** val snd : ('a1 * 'a2) -> 'a2 **)

let snd = function
| (_, y) -> y

(** val length : 'a1 list -> int **)

let rec length = function
| [] -> 0
| _ :: l' -> Stdlib.Int.succ (length l')

(** val app : 'a1 list -> 'a1 list -> 'a1 list **)

let rec app l m =
  match l with
  | [] -> m
  | a :: l1 -> a :: (app l1 m)

(** val bool_dec : bool -> bool -> bool **)

let bool_dec b1 b2 =
  if b1 then if b2 then true else false else if b2 then false else true

module Nat =
 struct
 end

(** val in_dec : ('a1 -> 'a1 -> bool) -> 'a1 -> 'a1 list -> bool **)

let rec in_dec h a = function
| [] -> false
| y :: l0 -> let s = h y a in if s then true else in_dec h a l0

(** val nth : int -> 'a1 list -> 'a1 -> 'a1 **)

let rec nth n l default =
  (fun fO fS n -> if n=0 then fO () else fS (n-1))
    (fun _ -> match l with
              | [] -> default
              | x :: _ -> x)
    (fun m -> match l with
              | [] -> default
              | _ :: t -> nth m t default)
    n

(** val concat : 'a1 list list -> 'a1 list **)

let rec concat = function
| [] -> []
| x :: l0 -> app x (concat l0)

(** val list_eq_dec : ('a1 -> 'a1 -> bool) -> 'a1 list -> 'a1 list -> bool **)

let rec list_eq_dec eq_dec l l' =
  match l with
  | [] -> (match l' with
           | [] -> true
           | _ :: _ -> false)
  | y :: l0 ->
    (match l' with
     | [] -> false
     | a :: l1 -> if eq_dec y a then list_eq_dec eq_dec l0 l1 else false)

(** val map : ('a1 -> 'a2) -> 'a1 list -> 'a2 list **)

let rec map f0 = function
| [] -> []
| a :: t -> (f0 a) :: (map f0 t)

(** val existsb : ('a1 -> bool) -> 'a1 list -> bool **)

let rec existsb f0 = function
| [] -> false
| a :: l0 -> (||) (f0 a) (existsb f0 l0)

(** val filter : ('a1 -> bool) -> 'a1 list -> 'a1 list **)

let rec filter f0 = function
| [] -> []
| x :: l0 -> if f0 x then x :: (filter f0 l0) else filter f0 l0

(** val find : ('a1 -> bool) -> 'a1 list -> 'a1 option **)

let rec find f0 = function
| [] -> None
| x :: tl -> if f0 x then Some x else find f0 tl

(** val list_prod : 'a1 list -> 'a2 list -> ('a1 * 'a2) list **)

let rec list_prod l l' =
  match l with
  | [] -> []
  | x :: t -> app (map (fun y -> (x, y)) l') (list_prod t l')

(** val seq : int -> int -> int list **)

let rec seq start len =
  (fun fO fS n -> if n=0 then fO () else fS (n-1))
    (fun _ -> [])
    (fun len0 -> start :: (seq (Stdlib.Int.succ start) len0))
    len

(** val repeat : 'a1 -> int -> 'a1 list **)

let rec repeat x n =
  (fun fO fS n -> if n=0 then fO () else fS (n-1))
    (fun _ -> [])
    (fun k -> x :: (repeat x k))
    n

type role = int

type capN = int

type lab = int

(** val add_new : ('a1 -> 'a1 -> bool) -> 'a1 list -> 'a1 list -> 'a1 list **)

let rec add_new a_dec s = function
| [] -> s
| x :: t -> add_new a_dec (if in_dec a_dec x s then s else x :: s) t

(** val expand' :
    ('a1 -> 'a1 -> bool) -> ('a1 -> 'a1 list) -> 'a1 list -> 'a1 list **)

let expand' a_dec succ s =
  add_new a_dec s (concat (map succ s))

(** val iter' :
    ('a1 -> 'a1 -> bool) -> ('a1 -> 'a1 list) -> int -> 'a1 list -> 'a1 list **)

let rec iter' a_dec succ n s =
  (fun fO fS n -> if n=0 then fO () else fS (n-1))
    (fun _ -> s)
    (fun k ->
    let s' = expand' a_dec succ s in
    if (=) (length s') (length s) then s else iter' a_dec succ k s')
    n

(** val decide' :
    ('a1 -> 'a1 -> bool) -> ('a1 -> 'a1 list) -> 'a1 list -> ('a1 -> bool) ->
    'a1 -> bool **)

let decide' a_dec succ all hb x =
  existsb hb (iter' a_dec succ (length all) (x :: []))

type ('node, 'w) pS' = ('node * 'w) * int

(** val ps_dec :
    ('a1 -> 'a1 -> bool) -> ('a2 -> 'a2 -> bool) -> ('a1, 'a2) pS' -> ('a1,
    'a2) pS' -> bool **)

let ps_dec node_dec w_dec x y =
  let (a, b) = x in
  let (p, n) = y in
  if let (a0, b0) = a in
     let (n0, w) = p in if node_dec a0 n0 then w_dec b0 w else false
  then (=) b n
  else false

(** val psucc :
    ('a1 -> 'a2 -> ('a1 * 'a2) list) -> ('a1 -> 'a2 -> ('a1 * 'a2) list) ->
    ('a1, 'a2) pS' -> ('a1, 'a2) pS' list **)

let psucc succ2 succ3 = function
| (p, b) ->
  let (n, w) = p in
  app (map (fun p0 -> (((fst p0), (snd p0)), b)) (succ2 n w))
    ((fun fO fS n -> if n=0 then fO () else fS (n-1))
       (fun _ -> [])
       (fun b' -> map (fun p0 -> (((fst p0), (snd p0)), b')) (succ3 n w))
       b)

(** val upto : int -> int list **)

let rec upto k =
  (fun fO fS n -> if n=0 then fO () else fS (n-1))
    (fun _ -> 0 :: [])
    (fun k' -> (Stdlib.Int.succ k') :: (upto k'))
    k

(** val all_ps : 'a1 list -> 'a2 list -> int -> ('a1, 'a2) pS' list **)

let all_ps nodes worlds k =
  concat
    (map (fun n ->
      concat (map (fun w -> map (fun b -> ((n, w), b)) (upto k)) worlds))
      nodes)

(** val phazb : ('a2 -> bool) -> ('a1, 'a2) pS' -> bool **)

let phazb hazb0 = function
| (p, _) -> let (_, w) = p in hazb0 w

(** val decide_reachb_fast :
    ('a1 -> 'a1 -> bool) -> ('a2 -> 'a2 -> bool) -> 'a1 list -> 'a2 list ->
    ('a1 -> 'a2 -> ('a1 * 'a2) list) -> ('a1 -> 'a2 -> ('a1 * 'a2) list) ->
    ('a2 -> bool) -> int -> 'a1 -> 'a2 -> bool **)

let decide_reachb_fast node_dec w_dec nodes worlds succ2 succ3 hazb0 k n w =
  decide' (ps_dec node_dec w_dec) (psucc succ2 succ3) (all_ps nodes worlds k)
    (phazb hazb0) ((n, w), k)

type 'gd gr =
| REnd
| RComm of role * role * ((lab * 'gd) * 'gd gr) list
| RAct of capN * role * 'gd gr
| RGoal of 'gd * 'gd gr
| RMu of 'gd gr
| RVar of int

(** val gr_rect_list :
    'a2 -> (role -> role -> ((lab * 'a1) * 'a1 gr) list -> 'a3 -> 'a2) ->
    (capN -> role -> 'a1 gr -> 'a2 -> 'a2) -> ('a1 -> 'a1 gr -> 'a2 -> 'a2)
    -> ('a1 gr -> 'a2 -> 'a2) -> (int -> 'a2) -> 'a3 -> (((lab * 'a1) * 'a1
    gr) -> ((lab * 'a1) * 'a1 gr) list -> 'a2 -> 'a3 -> 'a3) -> 'a1 gr -> 'a2 **)

let rec gr_rect_list hEnd hComm hAct hGoal hMu hVar hnil hcons = function
| REnd -> hEnd
| RComm (p, q, brs) ->
  hComm p q brs
    (let rec f0 = function
     | [] -> hnil
     | b :: bs' ->
       hcons b bs'
         (gr_rect_list hEnd hComm hAct hGoal hMu hVar hnil hcons (snd b))
         (f0 bs')
     in f0 brs)
| RAct (a, p, g0) ->
  hAct a p g0 (gr_rect_list hEnd hComm hAct hGoal hMu hVar hnil hcons g0)
| RGoal (g0, g1) ->
  hGoal g0 g1 (gr_rect_list hEnd hComm hAct hGoal hMu hVar hnil hcons g1)
| RMu g0 -> hMu g0 (gr_rect_list hEnd hComm hAct hGoal hMu hVar hnil hcons g0)
| RVar n -> hVar n

type 'gd env = 'gd gr option list

(** val subst : 'a1 env -> 'a1 gr -> 'a1 gr **)

let rec subst rho = function
| REnd -> REnd
| RComm (p, q, brs) ->
  RComm (p, q,
    (map (fun b -> (((fst (fst b)), (snd (fst b))), (subst rho (snd b)))) brs))
| RAct (a, p, g0) -> RAct (a, p, (subst rho g0))
| RGoal (g0, g1) -> RGoal (g0, (subst rho g1))
| RMu g0 -> RMu (subst (None :: rho) g0)
| RVar n -> (match nth n rho None with
             | Some m -> m
             | None -> RVar n)

(** val unfold_mu : 'a1 gr -> 'a1 gr **)

let unfold_mu g0 =
  subst ((Some (RMu g0)) :: []) g0

(** val close : 'a1 gr list -> 'a1 gr -> 'a1 gr **)

let close ctx g =
  subst (map (fun x -> Some x) ctx) g

(** val cands : 'a1 gr list -> 'a1 gr -> 'a1 gr list **)

let rec cands ctx g =
  (close ctx g) :: (match g with
                    | RComm (_, _, brs) ->
                      concat (map (fun b -> cands ctx (snd b)) brs)
                    | RAct (_, _, g0) -> cands ctx g0
                    | RGoal (_, g0) -> cands ctx g0
                    | RMu g0 -> cands ((close ctx (RMu g0)) :: ctx) g0
                    | _ -> [])

(** val gr_eq_dec : ('a1 -> 'a1 -> bool) -> 'a1 gr -> 'a1 gr -> bool **)

let gr_eq_dec gd_dec0 =
  gr_rect_list (fun g2 -> match g2 with
                          | REnd -> true
                          | _ -> false) (fun p q _ hl g2 ->
    match g2 with
    | RComm (r, r0, l) ->
      let s = (=) p r in
      if s then let s0 = (=) q r0 in if s0 then hl l else false else false
    | _ -> false) (fun a p _ iH g2 ->
    match g2 with
    | RAct (c, r, g) ->
      let s = (=) a c in
      if s then let s0 = (=) p r in if s0 then iH g else false else false
    | _ -> false) (fun g _ iH g2 ->
    match g2 with
    | RGoal (g0, g1) -> let s = gd_dec0 g g0 in if s then iH g1 else false
    | _ -> false) (fun _ iH g2 -> match g2 with
                                  | RMu g -> iH g
                                  | _ -> false) (fun n g2 ->
    match g2 with
    | RVar n0 -> (=) n n0
    | _ -> false) (fun brs' -> match brs' with
                               | [] -> true
                               | _ :: _ -> false) (fun b _ hb hbs brs' ->
    let (p, _) = b in
    let (l, g) = p in
    (match brs' with
     | [] -> false
     | p0 :: l0 ->
       let (p1, g0) = p0 in
       let (l1, g1) = p1 in
       let s = (=) l l1 in
       if s
       then let s0 = gd_dec0 g g1 in
            if s0
            then let s1 = hb g0 in if s1 then hbs l0 else false
            else false
       else false))

(** val succ0 :
    ('a2 -> 'a1 -> bool) -> (capN -> 'a1 -> 'a1 list) -> 'a2 gr -> 'a1 ->
    ('a2 gr * 'a1) list **)

let succ0 satb0 succE0 g w =
  match g with
  | RComm (_, _, brs) ->
    map (fun b -> ((snd b), w)) (filter (fun b -> satb0 (snd (fst b)) w) brs)
  | RAct (a, _, g0) -> map (fun w' -> (g0, w')) (succE0 a w)
  | RGoal (_, g0) -> (g0, w) :: []
  | RMu g0 -> ((unfold_mu g0), w) :: []
  | _ -> []

(** val succ1 :
    ('a2 -> 'a1 -> bool) -> 'a2 gr -> 'a1 -> ('a2 gr * 'a1) list **)

let succ1 satb0 g w =
  match g with
  | RComm (_, _, brs) ->
    map (fun b -> ((snd b), w))
      (filter (fun b -> negb (satb0 (snd (fst b)) w)) brs)
  | _ -> []

(** val decide_mu :
    ('a1 -> 'a1 -> bool) -> ('a2 -> 'a2 -> bool) -> 'a1 list -> ('a2 -> 'a1
    -> bool) -> (capN -> 'a1 -> 'a1 list) -> ('a1 -> bool) -> int -> 'a2 gr
    -> 'a1 -> bool **)

let decide_mu wd_dec0 gd_dec0 worlds satb0 succE0 hazb0 k g0 w =
  decide_reachb_fast (gr_eq_dec gd_dec0) wd_dec0 (cands [] g0) worlds
    (succ0 satb0 succE0) (succ1 satb0) hazb0 k g0 w

type wd = bool list

(** val wd_dec : wd -> wd -> bool **)

let wd_dec =
  list_eq_dec bool_dec

(** val wd_eqb : wd -> wd -> bool **)

let wd_eqb x y =
  if wd_dec x y then true else false

(** val wget : wd -> int -> bool **)

let wget w i =
  nth i w false

(** val wset : wd -> int -> bool -> wd **)

let rec wset w i v =
  match w with
  | [] -> []
  | b :: t ->
    ((fun fO fS n -> if n=0 then fO () else fS (n-1))
       (fun _ -> v :: t)
       (fun i' -> b :: (wset t i' v))
       i)

(** val set_all : bool -> int list -> wd -> wd **)

let rec set_all v is w =
  match is with
  | [] -> w
  | i :: t -> set_all v t (wset w i v)

type f =
| FTrue
| FAtom of int
| FAnd of f * f
| FOr of f * f
| FNot of f

(** val satf : f -> wd -> bool **)

let rec satf f0 w =
  match f0 with
  | FTrue -> true
  | FAtom i -> wget w i
  | FAnd (a, b) -> (&&) (satf a w) (satf b w)
  | FOr (a, b) -> (||) (satf a w) (satf b w)
  | FNot a -> negb (satf a w)

type act = { a_pre : f; a_add : int list; a_del : int list; a_haz : wd list }

(** val never : act **)

let never =
  { a_pre = (FNot FTrue); a_add = []; a_del = []; a_haz = [] }

(** val apply_act : int -> act -> wd -> wd **)

let apply_act hz a w =
  let w2 = set_all false a.a_del (set_all true a.a_add w) in
  if existsb (wd_eqb w2) a.a_haz then wset w2 hz true else w2

(** val succE : int -> act list -> capN -> wd -> wd list **)

let succE hz tbl a w =
  let ac = nth a tbl never in
  if satf ac.a_pre w then (apply_act hz ac w) :: [] else []

(** val hazb : int -> wd -> bool **)

let hazb hz w =
  wget w hz

type gd = wd list

(** val gd_dec : gd -> gd -> bool **)

let gd_dec =
  list_eq_dec wd_dec

(** val satb : gd -> wd -> bool **)

let satb g w =
  existsb (wd_eqb w) g

(** val all_bits : int -> wd list **)

let rec all_bits n =
  (fun fO fS n -> if n=0 then fO () else fS (n-1))
    (fun _ -> [] :: [])
    (fun k ->
    app (map (fun x -> true :: x) (all_bits k))
      (map (fun x -> false :: x) (all_bits k)))
    n

(** val kernel_hazard :
    int -> int -> act list -> int -> gd gr -> wd -> bool **)

let kernel_hazard n hz tbl k g0 w0 =
  decide_mu wd_dec gd_dec (all_bits n) satb (succE hz tbl) (hazb hz) k g0 w0

(** val kernel_first :
    int -> int -> act list -> int -> gd gr -> wd -> int option **)

let kernel_first n hz tbl kmax g0 w0 =
  find (fun k -> kernel_hazard n hz tbl k g0 w0)
    (seq 0 (Stdlib.Int.succ kmax))

type gW = gd gr * wd

(** val gW_dec : gW -> gW -> bool **)

let gW_dec x y =
  let (g, w) = x in
  let (g0, w0) = y in
  let s = gr_eq_dec gd_dec g g0 in if s then wd_dec w w0 else false

(** val gsucc : int -> act list -> gW -> gW list **)

let gsucc hz tbl s =
  app (succ0 satb (succE hz tbl) (fst s) (snd s)) (succ1 satb (fst s) (snd s))

(** val is_end : gd gr -> bool **)

let is_end = function
| REnd -> true
| _ -> false

(** val goal_hit : f -> gW -> bool **)

let goal_hit goal s =
  (&&) (is_end (fst s)) (satf goal (snd s))

(** val goal_reachable :
    int -> int -> act list -> f -> gd gr -> wd -> bool **)

let goal_reachable n hz tbl goal g w =
  decide' gW_dec (gsucc hz tbl) (list_prod (cands [] g) (all_bits n))
    (goal_hit goal) (g, w)

type raw =
| WEnd
| WAct of int * bool * role * raw
| WChoice of role * role * ((lab * f option) * raw) list
| WMu of raw
| WVar of int

type bCap = { b_pre : f; b_add : int list; b_del : int list }

(** val base_act : bCap -> act **)

let base_act b =
  { a_pre = b.b_pre; a_add = b.b_add; a_del = b.b_del; a_haz = [] }

(** val never_b : bCap **)

let never_b =
  { b_pre = (FNot FTrue); b_add = []; b_del = [] }

(** val skel : gd -> raw -> gd gr **)

let rec skel all = function
| WEnd -> REnd
| WAct (c, _, p, g) -> RAct (c, p, (skel all g))
| WChoice (p, q, brs) ->
  RComm (p, q,
    (map (fun b -> (((fst (fst b)), all), (skel all (snd b)))) brs))
| WMu g -> RMu (skel all g)
| WVar i -> RVar i

type params = { p_n : int; p_hz : int; p_base : bCap list; p_goal : f;
                p_worlds : wd list }

(** val gr0 : params -> gd gr -> wd -> bool **)

let gr0 p g w =
  goal_reachable p.p_n p.p_hz (map base_act p.p_base) p.p_goal g w

(** val elab : params -> gd gr list -> raw -> act list -> gd gr * act list **)

let rec elab p ctx r acc =
  match r with
  | WEnd -> (REnd, acc)
  | WAct (c, irr, p0, g) ->
    let res = elab p ctx g acc in
    if irr
    then let cont = close ctx (skel p.p_worlds g) in
         let hz_tbl = filter (fun w -> negb (gr0 p cont w)) p.p_worlds in
         let b = nth c p.p_base never_b in
         let ac = { a_pre = b.b_pre; a_add = b.b_add; a_del = b.b_del;
           a_haz = hz_tbl }
         in
         ((RAct ((length (snd res)), p0, (fst res))),
         (app (snd res) (ac :: [])))
    else ((RAct (c, p0, (fst res))), (snd res))
  | WChoice (p0, q, brs) ->
    let res =
      let rec go bs acc0 =
        match bs with
        | [] -> ([], acc0)
        | b :: t ->
          let r1 = elab p ctx (snd b) acc0 in
          let g =
            match snd (fst b) with
            | Some f0 -> filter (fun w -> satf f0 w) p.p_worlds
            | None ->
              filter (fun w -> gr0 p (close ctx (skel p.p_worlds (snd b))) w)
                p.p_worlds
          in
          let r2 = go t (snd r1) in
          (((((fst (fst b)), g), (fst r1)) :: (fst r2)), (snd r2))
      in go brs acc
    in
    ((RComm (p0, q, (fst res))), (snd res))
  | WMu g ->
    let res = elab p ((close ctx (RMu (skel p.p_worlds g))) :: ctx) g acc in
    ((RMu (fst res)), (snd res))
  | WVar i -> ((RVar i), acc)

(** val reachable_worlds : params -> gd gr -> wd -> wd list **)

let reachable_worlds p g0 w0 =
  map snd
    (iter' gW_dec (gsucc p.p_hz (map base_act p.p_base))
      (length (list_prod (cands [] g0) p.p_worlds)) ((g0, w0) :: []))

(** val kernel_run :
    int -> bCap list -> f -> int list -> int -> raw -> int option **)

let kernel_run n_atoms base goal init kmax raw0 =
  let n = Stdlib.Int.succ n_atoms in
  let all = all_bits n in
  let w0 = set_all true init (repeat false n) in
  let p0 = { p_n = n; p_hz = n_atoms; p_base = base; p_goal = goal;
    p_worlds = all }
  in
  let ws = reachable_worlds p0 (skel all raw0) w0 in
  let ws' = app ws (map (fun w -> wset w n_atoms true) ws) in
  let p = { p_n = n; p_hz = n_atoms; p_base = base; p_goal = goal; p_worlds =
    ws' }
  in
  let res = elab p [] raw0 (map base_act base) in
  kernel_first n n_atoms (snd res) kmax (fst res) w0
