
val negb : bool -> bool

val fst : ('a1 * 'a2) -> 'a1

val snd : ('a1 * 'a2) -> 'a2

val length : 'a1 list -> int

val app : 'a1 list -> 'a1 list -> 'a1 list

val bool_dec : bool -> bool -> bool

module Nat :
 sig
 end

val in_dec : ('a1 -> 'a1 -> bool) -> 'a1 -> 'a1 list -> bool

val nth : int -> 'a1 list -> 'a1 -> 'a1

val concat : 'a1 list list -> 'a1 list

val list_eq_dec : ('a1 -> 'a1 -> bool) -> 'a1 list -> 'a1 list -> bool

val map : ('a1 -> 'a2) -> 'a1 list -> 'a2 list

val existsb : ('a1 -> bool) -> 'a1 list -> bool

val filter : ('a1 -> bool) -> 'a1 list -> 'a1 list

val find : ('a1 -> bool) -> 'a1 list -> 'a1 option

val list_prod : 'a1 list -> 'a2 list -> ('a1 * 'a2) list

val seq : int -> int -> int list

val repeat : 'a1 -> int -> 'a1 list

type role = int

type capN = int

type lab = int

val add_new : ('a1 -> 'a1 -> bool) -> 'a1 list -> 'a1 list -> 'a1 list

val expand' :
  ('a1 -> 'a1 -> bool) -> ('a1 -> 'a1 list) -> 'a1 list -> 'a1 list

val iter' :
  ('a1 -> 'a1 -> bool) -> ('a1 -> 'a1 list) -> int -> 'a1 list -> 'a1 list

val decide' :
  ('a1 -> 'a1 -> bool) -> ('a1 -> 'a1 list) -> 'a1 list -> ('a1 -> bool) ->
  'a1 -> bool

type ('node, 'w) pS' = ('node * 'w) * int

val ps_dec :
  ('a1 -> 'a1 -> bool) -> ('a2 -> 'a2 -> bool) -> ('a1, 'a2) pS' -> ('a1,
  'a2) pS' -> bool

val psucc :
  ('a1 -> 'a2 -> ('a1 * 'a2) list) -> ('a1 -> 'a2 -> ('a1 * 'a2) list) ->
  ('a1, 'a2) pS' -> ('a1, 'a2) pS' list

val upto : int -> int list

val all_ps : 'a1 list -> 'a2 list -> int -> ('a1, 'a2) pS' list

val phazb : ('a2 -> bool) -> ('a1, 'a2) pS' -> bool

val decide_reachb_fast :
  ('a1 -> 'a1 -> bool) -> ('a2 -> 'a2 -> bool) -> 'a1 list -> 'a2 list ->
  ('a1 -> 'a2 -> ('a1 * 'a2) list) -> ('a1 -> 'a2 -> ('a1 * 'a2) list) ->
  ('a2 -> bool) -> int -> 'a1 -> 'a2 -> bool

type 'gd gr =
| REnd
| RComm of role * role * ((lab * 'gd) * 'gd gr) list
| RAct of capN * role * 'gd gr
| RGoal of 'gd * 'gd gr
| RMu of 'gd gr
| RVar of int

val gr_rect_list :
  'a2 -> (role -> role -> ((lab * 'a1) * 'a1 gr) list -> 'a3 -> 'a2) -> (capN
  -> role -> 'a1 gr -> 'a2 -> 'a2) -> ('a1 -> 'a1 gr -> 'a2 -> 'a2) -> ('a1
  gr -> 'a2 -> 'a2) -> (int -> 'a2) -> 'a3 -> (((lab * 'a1) * 'a1 gr) ->
  ((lab * 'a1) * 'a1 gr) list -> 'a2 -> 'a3 -> 'a3) -> 'a1 gr -> 'a2

type 'gd env = 'gd gr option list

val subst : 'a1 env -> 'a1 gr -> 'a1 gr

val unfold_mu : 'a1 gr -> 'a1 gr

val close : 'a1 gr list -> 'a1 gr -> 'a1 gr

val cands : 'a1 gr list -> 'a1 gr -> 'a1 gr list

val gr_eq_dec : ('a1 -> 'a1 -> bool) -> 'a1 gr -> 'a1 gr -> bool

val succ0 :
  ('a2 -> 'a1 -> bool) -> (capN -> 'a1 -> 'a1 list) -> 'a2 gr -> 'a1 -> ('a2
  gr * 'a1) list

val succ1 : ('a2 -> 'a1 -> bool) -> 'a2 gr -> 'a1 -> ('a2 gr * 'a1) list

val decide_mu :
  ('a1 -> 'a1 -> bool) -> ('a2 -> 'a2 -> bool) -> 'a1 list -> ('a2 -> 'a1 ->
  bool) -> (capN -> 'a1 -> 'a1 list) -> ('a1 -> bool) -> int -> 'a2 gr -> 'a1
  -> bool

type wd = bool list

val wd_dec : wd -> wd -> bool

val wd_eqb : wd -> wd -> bool

val wget : wd -> int -> bool

val wset : wd -> int -> bool -> wd

val set_all : bool -> int list -> wd -> wd

type f =
| FTrue
| FAtom of int
| FAnd of f * f
| FOr of f * f
| FNot of f

val satf : f -> wd -> bool

type act = { a_pre : f; a_add : int list; a_del : int list; a_haz : wd list }

val never : act

val apply_act : int -> act -> wd -> wd

val succE : int -> act list -> capN -> wd -> wd list

val hazb : int -> wd -> bool

type gd = wd list

val gd_dec : gd -> gd -> bool

val satb : gd -> wd -> bool

val all_bits : int -> wd list

val kernel_hazard : int -> int -> act list -> int -> gd gr -> wd -> bool

val kernel_first : int -> int -> act list -> int -> gd gr -> wd -> int option

type gW = gd gr * wd

val gW_dec : gW -> gW -> bool

val gsucc : int -> act list -> gW -> gW list

val is_end : gd gr -> bool

val goal_hit : f -> gW -> bool

val goal_reachable : int -> int -> act list -> f -> gd gr -> wd -> bool

type raw =
| WEnd
| WAct of int * bool * role * raw
| WChoice of role * role * ((lab * f option) * raw) list
| WMu of raw
| WVar of int

type bCap = { b_pre : f; b_add : int list; b_del : int list }

val base_act : bCap -> act

val never_b : bCap

val skel : gd -> raw -> gd gr

type params = { p_n : int; p_hz : int; p_base : bCap list; p_goal : f;
                p_worlds : wd list }

val gr0 : params -> gd gr -> wd -> bool

val elab : params -> gd gr list -> raw -> act list -> gd gr * act list

val reachable_worlds : params -> gd gr -> wd -> wd list

val kernel_run : int -> bCap list -> f -> int list -> int -> raw -> int option
