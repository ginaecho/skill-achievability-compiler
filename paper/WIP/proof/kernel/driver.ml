(* driver.ml -- parses the exporter's S-expression (src/skillc/kernel.py)
   and runs the extracted, verified kernel_run.  Prints "hazard k" for
   the least budget at which a hazard is reachable, or "none". *)
open Kernel

type sx = A of string | L of sx list

let tokenize s =
  let buf = Buffer.create 16 and toks = ref [] in
  let flush () = if Buffer.length buf > 0 then (toks := Buffer.contents buf :: !toks; Buffer.clear buf) in
  String.iter (fun c -> match c with
    | '(' | ')' -> flush (); toks := String.make 1 c :: !toks
    | ' ' | '\n' | '\t' | '\r' -> flush ()
    | c -> Buffer.add_char buf c) s;
  flush (); List.rev !toks

let parse toks =
  let rec go toks = match toks with
    | [] -> failwith "eof"
    | "(" :: rest ->
        let rec items acc rest = match rest with
          | ")" :: rest -> (L (List.rev acc), rest)
          | _ -> let (x, rest) = go rest in items (x :: acc) rest in
        items [] rest
    | ")" :: _ -> failwith "unexpected )"
    | t :: rest -> (A t, rest) in
  fst (go toks)

let rec formula = function
  | A "true" -> FTrue
  | L [A "atom"; A i] -> FAtom (int_of_string i)
  | L [A "and"; a; b] -> FAnd (formula a, formula b)
  | L [A "or"; a; b] -> FOr (formula a, formula b)
  | L [A "not"; a] -> FNot (formula a)
  | _ -> failwith "formula"

let ints = List.map (function A i -> int_of_string i | _ -> failwith "int")

let cap = function
  | L [L (A "pre" :: [p]); L (A "add" :: adds); L (A "del" :: dels)] ->
      { b_pre = formula p; b_add = ints adds; b_del = ints dels }
  | _ -> failwith "cap"

let rec raw = function
  | A "end" -> WEnd
  | L [A "act"; A c; A irr; A r; k] -> WAct (int_of_string c, irr = "1", int_of_string r, raw k)
  | L [A "choice"; A p; A q; L brs] ->
      WChoice (int_of_string p, int_of_string q,
               List.map (function
                 | L [A l; g; k] ->
                     let g' = (match g with A "none" -> None | f -> Some (formula f)) in
                     ((int_of_string l, g'), raw k)
                 | _ -> failwith "branch") brs)
  | L [A "mu"; k] -> WMu (raw k)
  | L [A "var"; A i] -> WVar (int_of_string i)
  | _ -> failwith "raw"

let field name = function
  | L (A "pack" :: fields) ->
      (match List.find_opt (function L (A n :: _) -> n = name | _ -> false) fields with
       | Some (L (_ :: rest)) -> rest | _ -> failwith ("missing " ^ name))
  | _ -> failwith "pack"

let () =
  let s = In_channel.input_all stdin in
  let p = parse (tokenize s) in
  let n = (match field "atoms" p with [A n] -> int_of_string n | _ -> failwith "atoms") in
  let caps = List.map cap (field "caps" p) in
  let goal = (match field "goal" p with [g] -> formula g | _ -> failwith "goal") in
  let init = ints (field "init" p) in
  let kmax = (match field "kmax" p with [A k] -> int_of_string k | _ -> failwith "kmax") in
  let proto = (match field "proto" p with [r] -> raw r | _ -> failwith "proto") in
  match kernel_run n caps goal init kmax proto with
  | Some k -> Printf.printf "hazard %d\n" k
  | None -> print_string "none\n"
